# Broker

Only needed for live mode; the experiments run offline.

## If Windows blocks Mosquitto ("An Application Control policy has blocked this file")

Use the Python broker instead; it runs inside the project's virtual environment:

    pip install amqtt
    python -m live.broker          # leave this terminal open, run the demo in a second one

No passwords or topic rules (local testing only). Live alerts and latency are the same as with
Mosquitto on our test runs. For the ACL demo, use Docker: `docker compose up -d broker` runs Mosquitto
with `broker/acl` and a password per component (see the main README).

## Install (Windows)

Install Eclipse Mosquitto from https://mosquitto.org/download/ (the Windows installer puts it in
`C:\Program Files\mosquitto`). Don't start the Windows service it installs, or stop it, because it
also listens on 1883: `net stop mosquitto` (admin terminal).

## Quick test broker (no passwords)

From the repository root:

    & "C:\Program Files\mosquitto\mosquitto.exe" -c broker/mosquitto-dev.conf -v

## With the information firewall (passwords + topic rules)

Create the password file locally (it is not committed):

    mosquitto_passwd -c broker/passwd sensor_emulator
    mosquitto_passwd broker/passwd twin
    mosquitto_passwd broker/passwd simulator
    mosquitto_passwd broker/passwd evaluator

Run the broker from the repository root:

    mosquitto -c broker/mosquitto.conf

Then give each live component its user, e.g. `--user twin --password ...` for `live.twin_service`.
With this config the twin cannot subscribe to `sim/#`.
