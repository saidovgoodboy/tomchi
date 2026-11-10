#include <WiFi.h>
#include <HTTPClient.h>
#include <Arduino.h>

const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://192.168.1.50:8000/api/detect";
const char* DEVICE_KEY = "TOMCHI_DEMO_KEY";
const char* BOX_ID = "box-1";
const int PIR_PIN = 13;
unsigned long lastDetectionMs = 0;
const unsigned long DETECTION_COOLDOWN_MS = 5000;

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  Serial.print("Connected; box ");
  Serial.println(BOX_ID);
}

void sendDetection() {
  HTTPClient http;
  http.begin(SERVER_URL);
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  http.addHeader("X-Box-Id", BOX_ID);

  // ANPR integration is still a mock: replace with plate OCR/camera image upload.
  String payload = "{\"plate\":\"01A123BC\"}";
  int httpCode = http.POST(payload);

  if (httpCode > 0 && httpCode < 300) {
    String res = http.getString();
    Serial.println(res);
  } else {
    Serial.printf("Detection request failed: HTTP %d\n", httpCode);
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIR_PIN, INPUT);
  connectWiFi();
}

void loop() {
  int motion = digitalRead(PIR_PIN);
  if (motion == HIGH && millis() - lastDetectionMs >= DETECTION_COOLDOWN_MS) {
    lastDetectionMs = millis();
    Serial.println("Motion detected. Sending mock plate detection...");
    sendDetection();
  }
  delay(200);
}
