#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

// Configure these values for each wash box before flashing.
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://192.168.1.50:8000";
const char* DEVICE_KEY = "CHANGE_ME";
const char* BOX_ID = "box-1";
const char* SERVER_ROOT_CA = "";

constexpr int BUTTON_PIN = 32;
constexpr uint16_t PANEL_WIDTH = 32;
constexpr uint16_t PANEL_HEIGHT = 16;
constexpr uint8_t PANEL_CHAIN = 1;
constexpr uint32_t DISPLAY_POLL_MS = 1000;
constexpr uint32_t SCROLL_INTERVAL_MS = 45;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 50;
constexpr bool ENABLE_BONUS_REDEMPTION = false;
// Match the bill acceptor's pulse-frequency timing preset; output remains disabled.
constexpr uint16_t PULSE_PERIOD_MS = 100;
static_assert(
    PULSE_PERIOD_MS == 50 || PULSE_PERIOD_MS == 100 || PULSE_PERIOD_MS == 200,
    "PULSE_PERIOD_MS must be 50, 100, or 200 ms");

// Common HUB75 pin map. Check the exact panel/controller pinout before wiring.
static HUB75_I2S_CFG::i2s_pins panelPins = {
    25, 26, 27, 14, 12, 13, 23, 19, 5, 17, -1, 4, 15, 16
};
static HUB75_I2S_CFG panelConfig(PANEL_WIDTH, PANEL_HEIGHT, PANEL_CHAIN);
static MatrixPanel_I2S_DMA panel(panelConfig);
static WiFiClient plainClient;
static WiFiClientSecure secureClient;

String displayText = "TOMCHI";
String lastRenderedText;
uint32_t lastDisplayPollAt = 0;
uint32_t lastScrollAt = 0;
uint32_t lastWiFiAttemptAt = 0;
bool wifiAttempted = false;
uint32_t lastDebounceAt = 0;
int lastButtonReading = HIGH;
int stableButtonState = HIGH;
int scrollX = PANEL_WIDTH;
bool bonusDisplay = false;

String endpointUrl(const char* path) {
  return String(SERVER_URL) + path;
}

bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  const uint32_t now = millis();
  if (wifiAttempted && now - lastWiFiAttemptAt < WIFI_RETRY_MS) return false;
  lastWiFiAttemptAt = now;
  wifiAttempted = true;
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  return false;
}

bool beginServerRequest(HTTPClient& http, const char* path) {
  if (!connectWiFi()) return false;
  const String url = endpointUrl(path);
  if (url.startsWith("https://")) {
    if (SERVER_ROOT_CA[0] == '\0') {
      Serial.println("Set SERVER_ROOT_CA before using HTTPS");
      return false;
    }
    secureClient.setCACert(SERVER_ROOT_CA);
    if (!http.begin(secureClient, url)) return false;
  } else if (!http.begin(plainClient, url)) {
    return false;
  }
  http.setTimeout(4000);
  http.addHeader("X-Device-Key", DEVICE_KEY);
  http.addHeader("X-Box-Id", BOX_ID);
  return true;
}

bool beginRequest(HTTPClient& http, const char* path) {
  return beginServerRequest(http, path);
}

void setDisplay(const String& text, bool isBonus) {
  if (text.isEmpty()) return;
  if (displayText != text || bonusDisplay != isBonus) {
    displayText = text;
    bonusDisplay = isBonus;
    scrollX = PANEL_WIDTH;
    lastRenderedText = "";
  }
}

void fetchDisplay() {
  HTTPClient http;
  if (!beginRequest(http, "/api/display")) return;

  const int status = http.GET();
  if (status >= 200 && status < 300) {
    JsonDocument response;
    const DeserializationError error = deserializeJson(response, http.getString());
    if (!error) {
      const char* text = response["text"] | "";
      const char* state = response["status"] | "";
      setDisplay(String(text), String(state) == "bonus_active");
    } else {
      Serial.printf("Display JSON parse failed: %s\n", error.c_str());
    }
  } else {
    Serial.printf("Display request failed: HTTP %d\n", status);
  }
  http.end();
}

void requestBonus() {
  HTTPClient http;
  if (!beginRequest(http, "/api/bonus/press")) {
    Serial.println("Server unavailable; bonus was not authorized");
    return;
  }

  http.addHeader("Content-Type", "application/json");
  const int status = http.POST("{}");
  if (status >= 200 && status < 300) {
    JsonDocument response;
    const String body = http.getString();
    const DeserializationError error = deserializeJson(response, body);
    if (!error && response["ok"] == true) {
      const int amount = response["amount"] | 0;
      const int pulseCount = response["pulse_count"] | 0;
      const int bonusLeft = response["bonus_left"] | 0;
      Serial.printf("Bonus approved: %d so'm, %d impulses; no physical impulses are emitted by this firmware\n",
                    amount, pulseCount);
      if (bonusLeft > 0) {
        setDisplay("BONUS QOLDI: " + String(bonusLeft) + " SO'M", true);
      } else {
        setDisplay("BONUS TUGADI", false);
      }
    } else if (!error) {
      const char* message = response["message"] | "Bonus not available";
      Serial.printf("Bonus refused: %s\n", message);
    } else {
      Serial.printf("Bonus response parse failed: %s\n", error.c_str());
    }
  } else {
    Serial.printf("Bonus request failed: HTTP %d; no physical impulses emitted\n", status);
  }
  http.end();
}

void pollButton() {
  const int reading = digitalRead(BUTTON_PIN);
  if (reading != lastButtonReading) lastDebounceAt = millis();

  if (millis() - lastDebounceAt >= BUTTON_DEBOUNCE_MS &&
      reading != stableButtonState) {
    stableButtonState = reading;
    if (stableButtonState == LOW) {
      if (ENABLE_BONUS_REDEMPTION) requestBonus();
      else Serial.println("Button detected; bonus request disabled until main-board pulse output is implemented");
    }
  }

  lastButtonReading = reading;
}

void scrollDisplay() {
  const uint32_t now = millis();
  if (now - lastScrollAt < SCROLL_INTERVAL_MS) return;
  lastScrollAt = now;

  panel.fillScreen(0);
  panel.setTextSize(1);
  panel.setTextWrap(false);
  panel.setTextColor(bonusDisplay
                         ? panel.color565(255, 190, 40)
                         : panel.color565(80, 230, 255));
  panel.setCursor(scrollX, 4);
  panel.print(displayText);

  const int textWidth = static_cast<int>(displayText.length()) * 6;
  if (scrollX < -textWidth) scrollX = PANEL_WIDTH;
  else scrollX--;
}

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  WiFi.mode(WIFI_STA);

  panelConfig.gpio = panelPins;
  panelConfig.clkphase = false;
  panelConfig.double_buff = false;
  panel.begin();
  panel.setBrightness8(80);
  panel.clearScreen();

  connectWiFi();
  Serial.printf("Tomchi panel ready for %s\n", BOX_ID);
  Serial.printf("Pulse-frequency preset: %u ms; physical output remains disabled\n",
                static_cast<unsigned>(PULSE_PERIOD_MS));
}

void loop() {
  connectWiFi();
  pollButton();

  const uint32_t now = millis();
  if (WiFi.status() == WL_CONNECTED &&
      now - lastDisplayPollAt >= DISPLAY_POLL_MS) {
    lastDisplayPollAt = now;
    fetchDisplay();
  }

  scrollDisplay();
  delay(2);
}
