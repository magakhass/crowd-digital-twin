# Broker

Create the password file locally (it is not committed):

    mosquitto_passwd -c broker/passwd sensor_emulator
    mosquitto_passwd broker/passwd twin
    mosquitto_passwd broker/passwd unity
    mosquitto_passwd broker/passwd evaluator

Run the broker from the repository root:

    mosquitto -c broker/mosquitto.conf
