# Unofficial Corvus GUI

A small desktop app that puts a form in front of CTRE's [`corvus`](https://v6.docs.ctr-electronics.com/en/stable/docs/api-reference/mechanisms/index.html) command-line tool. Pick a mechanism (elevator, arm, flywheel, ...), fill in the values, choose where to save the file, and get a generated Phoenix 6 **Java** subsystem.

> **This is an unofficial community project. It is not maintained, endorsed, or supported by CTR Electronics.**
> "CTRE", "Phoenix" and "corvus" belong to CTR Electronics. This project only calls the `corvus` tool that you download yourself.

## corvus is NOT included

CTR Electronics does not allow redistributing `corvus`, so this project does not include it and never will.
Download the latest `corvus` for your WPILib version from CTRE's [CLI Tools page](https://docs.ctr-electronics.com/cli-tools).
`corvus` is a standalone tool and does not need Python.

Use of `corvus` is covered by the [CTRE Software License Agreement](https://github.com/CrossTheRoadElec/Phoenix-Releases/blob/master/CTRE_LICENSE.txt).

## Features

- Mechanism dropdown filled straight from `corvus --help`, so new mechanisms show up automatically
- The form is built from the JSON template that `corvus json <mechanism>` produces: one input per value
- Dropdowns where it makes sense (for example Brake/Coast for `NeutralMode`)
- Names and types are locked and units are hidden, but all of them are sent to `corvus` unchanged
- "+ Add" buttons only on lists that can really hold more than one item (motor controllers, setpoints)
- Save dialog to choose where the `.java` file goes
- Log box showing everything `corvus` prints, including errors
- "Get corvus (CTRE)..." button that opens CTRE's download page

Output is always Java for now.

## Requirements

- Windows, macOS or Linux
- `corvus` from CTRE's [CLI Tools page](https://docs.ctr-electronics.com/cli-tools)
- Only if you run from source: Python 3.9+ with tkinter (included in the standard python.org installer)

## Run from source

1. Download `corvus` from CTRE (link above) and put it in the same folder as `corvus_gui.py`.
2. Run:

```
py corvus_gui.py
```

or

```
python corvus_gui.py
```

If `corvus` is somewhere else, click **Browse for corvus...** once. The choice is remembered in `corvus_gui_config.json` next to the program.

`corvus` is looked up in this order: the path you last chose, the folder of the program, then your `PATH`.

## Build a Windows .exe (optional)

This makes one `.exe` of the GUI only. `corvus` is **not** bundled.

```
py -m pip install pyinstaller
py -m PyInstaller --onefile --windowed --name UnofficialCorvusGUI corvus_gui.py
```

The result is `dist/UnofficialCorvusGUI.exe`. Put the `corvus` you downloaded from CTRE in the same folder as the `.exe` (or use **Browse for corvus...**).

## How to use it

1. Choose a mechanism from the dropdown.
2. Fill in the form. Only values can be edited; names and types are fixed and units are hidden.
3. Click **Generate Java subsystem...** and choose where to save the file (it starts in `src/main/java/frc/robot/subsystems` if that folder exists).
4. The app runs `corvus <mechanism> java -i <spec>.json -o <your file>` for you.

The **Copy template JSON** button copies the raw template to the clipboard, which is handy when reporting a problem.

## Customizing

Near the top of `corvus_gui.py`:

| Setting            | What it does                                                                                                           |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `EXCLUDED_TYPES`   | Mechanisms hidden from the dropdown (`swerve` and `swerve-proj` by default; use Phoenix Tuner X for swerve instead)    |
| `FIELD_CHOICES`    | Fields that become dropdowns, and their options                                                                        |
| `REPEATABLE_LISTS` | Lists that get a "+ Add" button                                                                                        |
| `HIDDEN_FIELDS`    | Fields that are not shown (their value is still sent to corvus unchanged)                                              |

## Troubleshooting

- **"corvus not found"**: download it from CTRE's [CLI Tools page](https://docs.ctr-electronics.com/cli-tools), then put it next to the program or use **Browse for corvus...**.
- **Dropdown only shows a default list**: the app could not read `corvus --help`. The log box shows what corvus printed.
- **Generation fails**: the log box shows corvus's error message.

## License

The code in this repository is under the [MIT License](LICENSE). It does not cover `corvus` or any other CTRE software, which stays under CTRE's own license.