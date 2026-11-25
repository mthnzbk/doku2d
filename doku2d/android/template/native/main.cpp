#include <Python.h>
#include <SFML/System/NativeActivity.hpp>
#include <android/native_activity.h>
#include <android/log.h>
#include <filesystem>
#include <string>

namespace {
JavaVM* keyboardVm = nullptr;
jobject keyboardActivity = nullptr;
thread_local bool keyboardAttached = false;
jmethodID configureKeyboardMethod = nullptr;
jmethodID takeKeyboardEventMethod = nullptr;
jmethodID keyboardViewportHeightMethod = nullptr;

JNIEnv* keyboardEnvironment() {
    if (!keyboardVm) return nullptr;
    // SFML's Android key handler can detach this thread while translating
    // hardware keys. A JNIEnv cached across frames is then invalid.
    JNIEnv* env = nullptr;
    const auto status = keyboardVm->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6);
    if (status == JNI_OK) return env;
    if (status != JNI_EDETACHED || keyboardVm->AttachCurrentThread(&env, nullptr) != JNI_OK)
        return nullptr;
    keyboardAttached = true;
    return env;
}

PyObject* configureKeyboard(PyObject*, PyObject* args) {
    int session, mode, anchor, cursor, show;
    PyObject* text;
    if (!PyArg_ParseTuple(args, "iiUiip", &session, &mode, &text, &anchor, &cursor, &show))
        return nullptr;
    if (!keyboardActivity) Py_RETURN_NONE;
    JNIEnv* keyboardEnv = keyboardEnvironment();
    if (!keyboardEnv) Py_RETURN_NONE;
    // JNI's modified UTF-8 is incompatible with supplementary Unicode
    // characters. Move text across the bridge as UTF-16 instead.
    PyObject* utf16 = PyUnicode_AsUTF16String(text);
    if (!utf16) return nullptr;
    auto value = keyboardEnv->NewString(
        reinterpret_cast<const jchar*>(PyBytes_AS_STRING(utf16) + 2),
        static_cast<jsize>(PyBytes_GET_SIZE(utf16) / 2 - 1));
    Py_DECREF(utf16);
    if (value) {
        keyboardEnv->CallVoidMethod(keyboardActivity, configureKeyboardMethod,
                                    session, mode, value, anchor, cursor, static_cast<jboolean>(show));
        keyboardEnv->DeleteLocalRef(value);
    }
    if (keyboardEnv->ExceptionCheck()) {
        keyboardEnv->ExceptionClear();
        return PyErr_Format(PyExc_RuntimeError, "Android keyboard setup failed");
    }
    Py_RETURN_NONE;
}

PyObject* takeKeyboardEvent(PyObject*, PyObject*) {
    if (!keyboardActivity) Py_RETURN_NONE;
    JNIEnv* keyboardEnv = keyboardEnvironment();
    if (!keyboardEnv) Py_RETURN_NONE;
    auto value = static_cast<jstring>(keyboardEnv->CallObjectMethod(
        keyboardActivity, takeKeyboardEventMethod));
    if (keyboardEnv->ExceptionCheck()) {
        keyboardEnv->ExceptionClear();
        return PyErr_Format(PyExc_RuntimeError, "Unable to read Android keyboard events");
    }
    if (!value) Py_RETURN_NONE;
    const jchar* data = keyboardEnv->GetStringChars(value, nullptr);
    int byteOrder = -1;
    PyObject* result = data ? PyUnicode_DecodeUTF16(reinterpret_cast<const char*>(data),
        keyboardEnv->GetStringLength(value) * 2, "replace", &byteOrder) : PyErr_NoMemory();
    if (data) keyboardEnv->ReleaseStringChars(value, data);
    if (keyboardEnv->ExceptionCheck()) keyboardEnv->ExceptionClear();
    keyboardEnv->DeleteLocalRef(value);
    return result;
}

PyObject* keyboardViewportHeight(PyObject*, PyObject*) {
    if (!keyboardActivity) return PyLong_FromLong(0);
    JNIEnv* keyboardEnv = keyboardEnvironment();
    if (!keyboardEnv) return PyLong_FromLong(0);
    const auto height = keyboardEnv->CallIntMethod(
        keyboardActivity, keyboardViewportHeightMethod);
    if (keyboardEnv->ExceptionCheck()) {
        keyboardEnv->ExceptionClear();
        return PyLong_FromLong(0);
    }
    return PyLong_FromLong(height);
}

struct KeyboardThread {
    KeyboardThread() {
        auto* activity = sf::getNativeActivity();
        keyboardVm = activity->vm;
        JNIEnv* env = keyboardEnvironment();
        if (!env) return;
        auto activityClass = env->GetObjectClass(activity->clazz);
        if (!activityClass) {
            if (env->ExceptionCheck()) env->ExceptionClear();
            return;
        }
        configureKeyboardMethod = env->GetMethodID(
            activityClass, "configureKeyboard", "(IILjava/lang/String;IIZ)V");
        if (configureKeyboardMethod)
            takeKeyboardEventMethod = env->GetMethodID(activityClass, "takeKeyboardEvent", "()Ljava/lang/String;");
        if (takeKeyboardEventMethod)
            keyboardViewportHeightMethod = env->GetMethodID(activityClass, "getKeyboardViewportHeight", "()I");
        if (keyboardViewportHeightMethod) {
            // NativeActivity can release its own reference during Back or
            // shutdown while the game still polls the keyboard for a frame.
            keyboardActivity = env->NewGlobalRef(activity->clazz);
        }
        if (env->ExceptionCheck()) env->ExceptionClear();
        env->DeleteLocalRef(activityClass);
    }
    ~KeyboardThread() {
        JNIEnv* env = keyboardEnvironment();
        if (env && keyboardActivity) env->DeleteGlobalRef(keyboardActivity);
        keyboardActivity = nullptr;
        if (env && keyboardAttached) keyboardVm->DetachCurrentThread();
        keyboardVm = nullptr;
    }
};

PyObject* logMessage(PyObject*, PyObject* args) {
    const char* text;
    if (!PyArg_ParseTuple(args, "s", &text)) return nullptr;
    __android_log_write(ANDROID_LOG_INFO, "PySFML", text);
    Py_RETURN_NONE;
}
PyMethodDef methods[] = {
    {"log", logMessage, METH_VARARGS, "Write to Android logcat"},
    {"configure_keyboard", configureKeyboard, METH_VARARGS, "Set the Android IME state"},
    {"take_keyboard_event", takeKeyboardEvent, METH_NOARGS, "Read the next Android IME snapshot"},
    {"keyboard_viewport_height", keyboardViewportHeight, METH_NOARGS, "Visible height above the Android IME"},
    {nullptr}
};
PyModuleDef module = {PyModuleDef_HEAD_INIT, "_android_bridge", nullptr, -1, methods};
PyMODINIT_FUNC PyInit_android_bridge() { return PyModule_Create(&module); }

bool check(PyStatus status) {
    if (!PyStatus_Exception(status)) return true;
    __android_log_print(ANDROID_LOG_ERROR, "PySFML", "Python startup: %s", status.err_msg ? status.err_msg : "unknown error");
    return false;
}
}

int main(int, char**) {
    KeyboardThread keyboard;
    const std::string root = std::string(sf::getNativeActivity()->internalDataPath) + "/python-runtime";
    PyImport_AppendInittab("_android_bridge", PyInit_android_bridge);
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.parse_argv = 0;
    config.write_bytecode = 0;
    config.site_import = 0;
    config.module_search_paths_set = 1;
    bool ok = check(PyConfig_SetBytesString(&config, &config.home, root.c_str()));
    ok = ok && check(PyConfig_SetBytesString(&config, &config.program_name, "pysfml-android"));
    for (const char* suffix : {"/lib/python3.13", "/lib/python3.13/lib-dynload", "/site-packages", "/game"}) {
        const std::string path = root + suffix;
        wchar_t* wide = Py_DecodeLocale(path.c_str(), nullptr);
        if (!wide) { ok = false; break; }
        const PyStatus status = PyWideStringList_Append(&config.module_search_paths, wide);
        PyMem_RawFree(wide);
        if (!check(status)) { ok = false; break; }
    }
    if (ok) ok = check(Py_InitializeFromConfig(&config));
    PyConfig_Clear(&config);
    if (!ok) return 1;
    const int result = PyRun_SimpleString(
        "import sys, _android_bridge\n"
        "class AndroidLog:\n"
        "    def write(self, text):\n"
        "        if text.strip(): _android_bridge.log(text)\n"
        "        return len(text)\n"
        "    def flush(self): pass\n"
        "sys.stdout = sys.stderr = AndroidLog()\n"
        "print('PY_BOOT_OK', sys.version)\n"
        "import _doku2d_android_start\n"
    );
    if (result) PyErr_Print();
    Py_FinalizeEx();
    return result ? 1 : 0;
}
