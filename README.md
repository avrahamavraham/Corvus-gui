# Corvus GUI

A small desktop app that puts a form in front of CTRE's [`corvus`](https://v6.docs.ctr-electronics.com/en/stable/docs/api-reference/mechanisms/index.html) command-line tool. Pick a mechanism (elevator, arm, flywheel, ...), fill in the values, choose where to save the file, and get a generated Phoenix 6 **Java** subsystem.

> This is an unofficial community tool. It is not made by or affiliated with CTR Electronics.

## Features

- Mechanism dropdown filled straight from `corvus --help`, so new mechanisms show up automatically
- The form is built from the JSON template that `corvus json <mechanism>` produces: one input per value
- Dropdowns where it makes sense (for example Brake/Coast for `NeutralMode`)
- Names, types and units are shown but locked, so they can't be broken by accident
- "+ Add" buttons only on lists that can really hold more than one item (motor controllers, setpoints)
- Save dialog to choose where the `.java` file goes
- Log box showing everything `corvus` prints, including errors

Output is always Java for now.

## Requirements
- Python 3.9+ with tkinter (included in the standard python.org installer) if you run from source
- `corvus` from CTRE's [CLI tools download page](https://docs.ctr-electronics.com/cli-tools)

## Run from source

1. Download [`corvus`](https://docs.ctr-electronics.com/cli-tools) and put it in the same folder as `corvus_gui.py`.
2. Run:

   ```
   py corvus_gui.py
   ```
   or
   ```
   pthon corvus_gui.py
   ```

If `corvus` is somewhere else, click **Browse for corvus...** once. The choice is remembered in `corvus_gui_config.json` next to the program.

`corvus` is looked up in this order: the path you last chose, the packaged bundle, the folder of the program, then your `PATH`.

## How to use it

1. Choose a mechanism from the dropdown.
2. Fill in the form. Only values can be edited; names, types and units are fixed.
3. Click **Generate Java subsystem...** and choose where to save the file (it starts in `src/main/java/frc/robot/subsystems` if that folder exists).
4. The app runs `corvus <mechanism> java -i <spec>.json -o <your file>` for you.

The **Copy template JSON** button copies the raw template to the clipboard, which is handy when reporting a problem.

## Customizing

Near the top of `corvus_gui.py`:

| Setting | What it does |
|---|---|
| `EXCLUDED_TYPES` | Mechanisms hidden from the dropdown (`swerve` and `swerve-proj` by default sould both be used from phonix tuner x) |
| `FIELD_CHOICES` | Fields that become dropdowns, and their options |
| `REPEATABLE_LISTS` | Lists that get a "+ Add" button |
| `HIDDEN_FIELDS` | Fields that are not shown (their value is still sent to corvus unchanged) |

## Troubleshooting

- **"corvus not found"**: put `corvus` next to the program or use **Browse for corvus...**.
- **Dropdown only shows a default list**: the app could not read `corvus --help`. The log box shows what corvus printed.
- **Generation fails**: the log box shows corvus's error message.
