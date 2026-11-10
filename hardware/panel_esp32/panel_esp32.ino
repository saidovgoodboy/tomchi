#include <WiFi.h>
#include <HTTPClient.h>
#include <Arduino.h>
#include <ArduinoJson.h>

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://192.168.1.50:8000";
const char* DEVICE_KEY = "TOMCHI_DEMO_KEY";
const char* BOX_ID = "box-1";
const int BUTTON_PIN = 4;
const int OPTOCOUPLER_PIN = 26;
const unsigned long DEBOUNCE_MS = 50;
const unsigned long PULSE_ON_MS = 100;
const unsigned long PULSE_GAP_MS = 100;
const int MAX_PULSES_PER_PRESS = 100;

String currentText = "WAITING";
bool pulseSequenceRunning = false;

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

String fetchDisplayText() {
  HTTPClient http;
  String url = String(SERVER_URL) + "/api/display";
  http.begin(url);
  http.addHeader("X-Device-Key", DEVICE_KEY);
  http.addHeader("X-Box-Id", BOX_ID);
  http.setTimeout(3000);

  int code = http.GET();
  String payload = "";
  if (code > 0) {
    payload = http.getString();
  }
  http.end();
  return payload;
}

void sendBonusPress() {
  HTTPClient http;
  String url = String(SERVER_URL) + "/api/bonus/press";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  http.addHeader("X-Box-Id", BOX_ID);
  http.setTimeout(5000);

  String body = "{}";
  int code = http.POST(body);
  if (code > 0 && code < 300) {
    String response = http.getString();
    Serial.println(response);
    JsonDocument result;
    DeserializationError error = deserializeJson(result, response);
    int pulseCount = result["pulse_count"] | 0;
    if (!error && result["ok"] == true && pulseCount > 0 && pulseCount <= MAX_PULSES_PER_PRESS) {
      pulseSequenceRunning = true;
      for (int i = 0; i < pulseCount; i++) {
        digitalWrite(OPTOCOUPLER_PIN, HIGH);
        delay(PULSE_ON_MS);
        digitalWrite(OPTOCOUPLER_PIN, LOW);
        if (i + 1 < pulseCount) delay(PULSE_GAP_MS);
      }
      pulseSequenceRunning = false;
    } else {
      Serial.println("Server did not authorize bonus; no pulses sent");
    }
  } else {
    Serial.printf("Bonus request failed: HTTP %d; no pulses sent\n", code);
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  // Drive the optocoupler input only; never connect this GPIO directly to the main board.
  pinMode(OPTOCOUPLER_PIN, OUTPUT);
  digitalWrite(OPTOCOUPLER_PIN, LOW);
  connectWiFi();
  Serial.print("Connected; box ");
  Serial.println(BOX_ID);
}

void loop() {
  static int lastButtonState = HIGH;
  static int stableButtonState = HIGH;
  static unsigned long lastDebounceMs = 0;
  int reading = digitalRead(BUTTON_PIN);
  if (reading != lastButtonState) lastDebounceMs = millis();
  if (millis() - lastDebounceMs >= DEBOUNCE_MS && reading != stableButtonState) {
    stableButtonState = reading;
    if (!pulseSequenceRunning && stableButtonState == LOW) {
      Serial.println("Button pressed");
      sendBonusPress();
    }
  }
  lastButtonState = reading;

  String response = fetchDisplayText();
  if (response.length() > 0) {
    currentText = response;
    Serial.println(currentText);
  }
  delay(1000);
}
