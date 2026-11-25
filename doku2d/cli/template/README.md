# __APP_ID__

Run with the Python environment that has Doku2D installed:

```sh
python -m doku2d run
python -m doku2d build
```

A/D/W/S or arrow keys move. Collect the lights. F5 saves, F9 loads.
The buttons do the same. The hour slider changes the day/night cycle.
The group opacity slider fades the entire HUD as one surface.

Project settings are in `doku2d.toml`. Assets are in `assets/`.
The project starts with the Doku2D icon. Replace `assets/icon.png` for the game
window and `assets/icon.ico` for the Windows executable, or change the
`[window]` and `[build]` icon paths in the project settings.
Progress uses `game.saves`; user settings use `game.settings`.
Save files live in your OS user-data directory, separately from the game files.
You can set `[storage] directory = ".user-data"` to use a project-local folder.

`python -m doku2d build` compiles the project with Nuitka and prints the path to the
executable. Install Nuitka and a compatible C compiler first. Distribute the whole
`dist/<app_id>.dist` folder.
