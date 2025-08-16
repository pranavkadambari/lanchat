# LanChat

LanChat is a personal peer-to-peer chat application for local networks.
It lets users automatically discover peers on the same LAN, establish sessions, and chat through a simple graphical interface.

## Features

- Peer discovery on the local network
- Real-time messaging through a message bus
- Simple Tkinter-based graphical interface
- No central server required

## Running the Project

Simply run the entry point with Python:

```bash
python lanchat/run.py
```
This will start the Tkinter chat application. If other devices on the same network are running LanChat, they will be discovered automatically.

## Project Structure

```bash
lanchat/
│── lanchat/
│   ├── core/          # Networking, sessions, discovery, messaging
│   ├── ui/tk_app/     # Tkinter-based user interface
│   ├── run.py         # Entry point to start the app
│── README.md          # Project documentation

```

## Core Modules

discovery.py → Handles peer discovery on LAN

session.py → Manages sessions between peers

msgbus.py → Message handling system

transport.py → Data transport layer

tk_app/ → Tkinter GUI (chat app, views)

## Notes

This project is meant for experimentation and personal use.

It relies mainly on the Python standard library (plus Tkinter, which comes with most Python installations).

Should run on Windows, Linux, and macOS.
