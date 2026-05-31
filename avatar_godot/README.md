# A.R.I.A. Interactive Avatar (Godot 4.x)

This directory contains a Godot 4.x project that implements a beautiful, reactive, transparent digital avatar for A.R.I.A.

## Features
- **Real-Time Synchronization**: Connects to `ws://127.0.0.1:8000/ws/avatar` and reacts to A.R.I.A.'s internal agent states (`idle`, `thinking`, `analyzing`, `speaking`).
- **Procedural Graphics**: Zero external image dependencies! Visualized using Godot's 2D canvas drawing system (`_draw`), keeping the avatar extremely lightweight and responsive.
- **State Animations**:
  - `idle`: Calm cyan color breathing cycle with rotating segmented rings.
  - `thinking`: Rapidly counter-rotating rings and faster particle orbits in gold/yellow color.
  - `analyzing`: Horizontal scanning laser bar and green targeting bounding box in magenta/purple color.
  - `speaking`: Teal/green voice wave amplitude reactive pulse simulator.
- **Glassmorphic Transparency**: Supports borderless, transparent window overlaying on your desktop.

## Running / Editing the Avatar

### Prerequisites
Make sure you have **Godot 4.x** installed on your system.

### How to Run:
1. Start the main A.R.I.A. servers by running `./start.sh` in the repository root.
2. Run the Godot project using the Godot editor, or execute it from the CLI:
   ```bash
   # From this directory:
   godot --path ./
   ```

### Customizations:
- **WebSocket URL**: Modify the `ws_url` variable at the top of `avatar.gd` to target a remote server.
- **Window Size**: Open the project in Godot, go to `Project Settings` -> `Display` -> `Window`, and adjust the Width and Height.
- **Colors & Speeds**: Edit the `set_agent_state` method in `avatar.gd` to change color palettes or ring speeds.
