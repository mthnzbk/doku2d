package org.doku2d.pysfmldemo;

import android.app.NativeActivity;
import android.os.Bundle;
import android.os.Build;
import android.graphics.Color;
import android.graphics.Rect;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowInsets;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.json.JSONArray;

public class MainActivity extends NativeActivity {
    private final ConcurrentLinkedQueue<String> keyboardEvents = new ConcurrentLinkedQueue<>();
    private EditText keyboardEditor;
    private View previousFocus;
    private int keyboardSession;
    private int keyboardMode;
    private boolean applyingKeyboardState;
    private volatile int keyboardViewportHeight;
    private volatile boolean destroying;

    private void updateLegacyKeyboardViewport() {
        View decor = getWindow().getDecorView();
        Rect visible = new Rect();
        decor.getWindowVisibleDisplayFrame(visible);
        int[] origin = new int[2];
        decor.getLocationOnScreen(origin);
        int available = visible.bottom - origin[1];
        // Ignore the navigation bar when only the regular system UI is visible.
        keyboardViewportHeight = available > 0 && available < decor.getHeight() * .85
                ? available : 0;
    }

    public int getKeyboardViewportHeight() {
        return destroying ? 0 : keyboardViewportHeight;
    }

    private void sendKeyboardState(boolean submitted) {
        if (applyingKeyboardState || keyboardMode == 0) return;
        String text = keyboardEditor.getText().toString();
        int anchor = Math.min(text.length(), Math.max(0, keyboardEditor.getSelectionStart()));
        int cursor = Math.min(text.length(), Math.max(0, keyboardEditor.getSelectionEnd()));
        // Android selections count UTF-16 units. Python counts code points.
        keyboardEvents.offer(new JSONArray()
                .put(keyboardSession).put(text)
                .put(text.codePointCount(0, anchor)).put(text.codePointCount(0, cursor))
                .put(submitted).toString());
    }

    private void createKeyboardEditor() {
        keyboardEditor = new EditText(this) {
            @Override protected void onSelectionChanged(int anchor, int cursor) {
                super.onSelectionChanged(anchor, cursor);
                if (keyboardEditor != null) sendKeyboardState(false);
            }
        };
        // Only the IME uses this view. SFML continues drawing the actual field.
        keyboardEditor.setAlpha(0);
        keyboardEditor.setBackgroundColor(Color.TRANSPARENT);
        keyboardEditor.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        keyboardEditor.setFocusable(false);
        keyboardEditor.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence text, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence text, int start, int before, int count) {}
            @Override public void afterTextChanged(Editable text) { sendKeyboardState(false); }
        });
        keyboardEditor.setOnEditorActionListener((view, action, event) -> {
            if (keyboardMode == 2 || (action != EditorInfo.IME_ACTION_DONE &&
                    (event == null || event.getKeyCode() != KeyEvent.KEYCODE_ENTER))) return false;
            if (event == null || event.getAction() == KeyEvent.ACTION_DOWN) {
                sendKeyboardState(true);
                getSystemService(InputMethodManager.class)
                        .hideSoftInputFromWindow(keyboardEditor.getWindowToken(), 0);
            }
            return true;
        });
        addContentView(keyboardEditor, new FrameLayout.LayoutParams(1, 1));
        View decor = getWindow().getDecorView();
        if (Build.VERSION.SDK_INT >= 30) {
            decor.setOnApplyWindowInsetsListener((view, insets) -> {
                keyboardViewportHeight = insets.isVisible(WindowInsets.Type.ime())
                        ? Math.max(1, getWindowManager().getCurrentWindowMetrics().getBounds().height()
                                - insets.getInsets(WindowInsets.Type.ime()).bottom)
                        : 0;
                return view.onApplyWindowInsets(insets);
            });
        } else {
            decor.getViewTreeObserver().addOnGlobalLayoutListener(this::updateLegacyKeyboardViewport);
        }
    }

    public void configureKeyboard(int session, int mode, String text,
                                  int anchor, int cursor, boolean show) {
        // JNI calls originate from SFML's game thread. Android views stay on
        // the UI thread, and the game consumes snapshots through the queue.
        runOnUiThread(() -> {
            if (destroying) return;
            InputMethodManager ime = getSystemService(InputMethodManager.class);
            applyingKeyboardState = true;
            try {
                if (keyboardSession != session) keyboardEvents.clear();
                keyboardSession = session;
                if (mode == 0) {
                    keyboardMode = 0;
                    ime.hideSoftInputFromWindow(keyboardEditor.getWindowToken(), 0);
                    keyboardEditor.setText("");
                    keyboardEditor.setFocusable(false);
                    if (previousFocus != null) previousFocus.requestFocus();
                    previousFocus = null;
                    return;
                }
                if (keyboardMode == 0) previousFocus = getCurrentFocus();
                boolean changedMode = keyboardMode != mode;
                keyboardMode = mode;
                if (changedMode) {
                    int variation = mode == 3 ? InputType.TYPE_TEXT_VARIATION_PASSWORD :
                            mode == 2 ? InputType.TYPE_TEXT_FLAG_MULTI_LINE : 0;
                    keyboardEditor.setInputType(InputType.TYPE_CLASS_TEXT | variation);
                    keyboardEditor.setImeOptions(EditorInfo.IME_FLAG_NO_EXTRACT_UI |
                            (mode == 3 ? EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING : 0) |
                            (mode == 2 ? EditorInfo.IME_ACTION_NONE : EditorInfo.IME_ACTION_DONE));
                }
                if (!text.contentEquals(keyboardEditor.getText())) keyboardEditor.setText(text);
                keyboardEditor.setSelection(text.offsetByCodePoints(0, anchor),
                                            text.offsetByCodePoints(0, cursor));
                if (show) {
                    keyboardEditor.setFocusableInTouchMode(true);
                    keyboardEditor.requestFocus();
                    if (changedMode) ime.restartInput(keyboardEditor);
                    keyboardEditor.post(() -> {
                        if (keyboardMode != 0 && keyboardSession == session)
                            ime.showSoftInput(keyboardEditor, InputMethodManager.SHOW_IMPLICIT);
                    });
                } else if (changedMode) {
                    ime.restartInput(keyboardEditor);
                }
            } finally {
                applyingKeyboardState = false;
            }
        });
    }

    public String takeKeyboardEvent() {
        return destroying ? null : keyboardEvents.poll();
    }

    @Override protected void onDestroy() {
        destroying = true;
        keyboardEvents.clear();
        super.onDestroy();
    }

    private static void deleteTree(File file) throws IOException {
        File[] children = file.listFiles();
        if (children != null) {
            for (File child : children) deleteTree(child);
        }
        if (file.exists() && !file.delete()) throw new IOException("Cannot delete " + file);
    }

    private static String readText(InputStream in) throws IOException {
        try (InputStream source = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = source.read(buffer)) != -1) out.write(buffer, 0, count);
            return new String(out.toByteArray(), StandardCharsets.UTF_8).trim();
        }
    }

    @Override public void onCreate(Bundle state) {
        // NativeActivity loads the SFML/Python entry point in super.onCreate.
        // The Python standard library must be on disk before that happens.
        try {
            File destination = new File(getFilesDir(), "python-runtime");
            File marker = new File(destination, ".runtime-sha256");
            String expected;
            expected = readText(getAssets().open("runtime.sha256"));
            String actual = marker.exists() ? readText(new FileInputStream(marker)) : "";
            if (!actual.equals(expected)) {
                // Remove obsolete Python modules when the APK is updated.
                // Saves are stored in a separate directory under getFilesDir().
                deleteTree(destination);
                if (!destination.isDirectory() && !destination.mkdirs())
                    throw new IOException("Cannot create runtime directory");
                String base = destination.getCanonicalPath() + File.separator;
                try (ZipInputStream zip = new ZipInputStream(getAssets().open("runtime.zip"))) {
                    ZipEntry entry;
                    byte[] buffer = new byte[32768];
                    while ((entry = zip.getNextEntry()) != null) {
                        File target = new File(destination, entry.getName());
                        if (!target.getCanonicalPath().startsWith(base))
                            throw new IOException("Invalid runtime archive entry");
                        if (entry.isDirectory()) {
                            if (!target.isDirectory() && !target.mkdirs())
                                throw new IOException("Cannot create " + target);
                        } else {
                            File parent = target.getParentFile();
                            if (!parent.isDirectory() && !parent.mkdirs())
                                throw new IOException("Cannot create " + parent);
                            try (OutputStream out = new FileOutputStream(target)) {
                                int count;
                                while ((count = zip.read(buffer)) != -1) out.write(buffer, 0, count);
                            }
                        }
                    }
                }
                try (OutputStream out = new FileOutputStream(marker)) {
                    out.write(expected.getBytes(StandardCharsets.UTF_8));
                }
            }
        } catch (IOException error) {
            throw new RuntimeException("Python runtime extraction failed", error);
        }
        super.onCreate(state);
        createKeyboardEditor();
    }
}
