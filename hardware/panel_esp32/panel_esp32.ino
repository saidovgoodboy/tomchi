#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <string.h>

// Configure these values for each wash box before flashing.
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://192.168.1.50:8000";
const char* DEVICE_KEY = "CHANGE_ME";
const char* BOX_ID = "box-1";
const char* SERVER_ROOT_CA = "";

constexpr int BUTTON_PIN = 32;
constexpr int PULSE_OUTPUT_PIN = 33;
constexpr uint16_t PANEL_WIDTH = 32;
constexpr uint16_t PANEL_HEIGHT = 16;
constexpr uint8_t PANEL_CHAIN = 1;
constexpr uint32_t DISPLAY_POLL_MS = 1000;
constexpr uint32_t SCROLL_INTERVAL_MS = 45;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t BUTTON_DEBOUNCE_MS = 50;
constexpr uint16_t DEFAULT_PULSE_FREQUENCY_MS = 100;
constexpr bool DEFAULT_PULSE_ACTIVE_HIGH = true;

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
String displayRemainingLabel = "MUKOFOT QOLDI";
String displayFinishedText = "MUKOFOT TUGADI";
String displayCurrencyLabel = "SO'M";
uint32_t lastDisplayPollAt = 0;
uint32_t lastScrollAt = 0;
uint32_t lastWiFiAttemptAt = 0;
bool wifiAttempted = false;
volatile uint8_t pendingButtonPresses = 0;
volatile uint32_t lastButtonInterruptAt = 0;
int scrollX = PANEL_WIDTH;
bool bonusDisplay = false;
bool testModeActive = false;
uint16_t pulseFrequencyMs = DEFAULT_PULSE_FREQUENCY_MS;
bool pulseActiveHigh = DEFAULT_PULSE_ACTIVE_HIGH;

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

void setPulseIdle() {
  digitalWrite(PULSE_OUTPUT_PIN, pulseActiveHigh ? LOW : HIGH);
}

void emitPulses(int pulseCount) {
  if (pulseCount <= 0) return;

  const uint16_t activeMs = pulseFrequencyMs / 2;
  const uint16_t inactiveMs = pulseFrequencyMs - activeMs;
  const uint8_t activeLevel = pulseActiveHigh ? HIGH : LOW;
  const uint8_t inactiveLevel = pulseActiveHigh ? LOW : HIGH;

  for (int pulse = 0; pulse < pulseCount; pulse++) {
    digitalWrite(PULSE_OUTPUT_PIN, activeLevel);
    delay(activeMs);
    digitalWrite(PULSE_OUTPUT_PIN, inactiveLevel);
    delay(inactiveMs);
  }
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
      const char* polarity = response["pulse_polarity"] | "";
      const char* remainingLabel = response["display_remaining_label"] | "MUKOFOT QOLDI";
      const char* finishedText = response["display_finished_text"] | "MUKOFOT TUGADI";
      const char* currencyLabel = response["display_currency_label"] | "SO'M";
      const int frequencyMs = response["pulse_frequency_ms"] | pulseFrequencyMs;
      displayRemainingLabel = remainingLabel;
      displayFinishedText = finishedText;
      displayCurrencyLabel = currencyLabel;
      testModeActive = response["test_mode"] | false;
      const int testPulseCount = response["test_pulse_count"] | 0;
      if (strcmp(polarity, "HIGH") == 0) pulseActiveHigh = true;
      else if (strcmp(polarity, "LOW") == 0) pulseActiveHigh = false;
      if (frequencyMs == 50 || frequencyMs == 100 || frequencyMs == 200) {
        pulseFrequencyMs = static_cast<uint16_t>(frequencyMs);
      }
      setPulseIdle();
      if (testPulseCount > 0) {
        Serial.printf("Emitting %d admin test pulses\n", testPulseCount);
        emitPulses(testPulseCount);
      }
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
  // Bir bosish uchun bitta press_id: tarmoq xatosida qayta urinsak ham
  // server pulni ikki marta yechmaydi (idempotentlik).
  char pressId[32];
  snprintf(pressId, sizeof(pressId), "p-%08lx-%08lx",
           static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(millis()));
  const String body = String("{\"press_id\":\"") + pressId + "\"}";

  for (uint8_t attempt = 0; attempt < 3; attempt++) {
    HTTPClient http;
    if (!beginRequest(http, "/api/bonus/press")) {
      Serial.println("Server unavailable; bonus was not authorized");
      return;
    }

    http.addHeader("Content-Type", "application/json");
    const int status = http.POST(body);
    if (status >= 200 && status < 300) {
      JsonDocument response;
      const String payload = http.getString();
      const DeserializationError error = deserializeJson(response, payload);
      if (!error && response["ok"] == true) {
        const int amount = response["amount"] | 0;
        const int pulseCount = response["pulse_count"] | 0;
        const int bonusLeft = response["bonus_left"] | 0;
        const bool duplicate = response["duplicate"] | false;
        Serial.printf("Bonus approved: %d so'm, emitting %d pulses (%s active, %u ms period)%s\n",
                      amount,
                      pulseCount,
                      pulseActiveHigh ? "HIGH" : "LOW",
                      static_cast<unsigned>(pulseFrequencyMs),
                      duplicate ? " [duplicate]" : "");
        emitPulses(pulseCount);
        if (bonusLeft > 0) {
          setDisplay(displayRemainingLabel + ": " + String(bonusLeft) + " " + displayCurrencyLabel, true);
        } else {
          setDisplay(displayFinishedText, false);
        }
      } else if (!error) {
        const char* message = response["message"] | "Bonus not available";
        Serial.printf("Bonus refused: %s\n", message);
        setDisplay(String(message), false);
      } else {
        Serial.printf("Bonus response parse failed: %s\n", error.c_str());
        setDisplay("SERVER XATOSI", false);
      }
      http.end();
      return;
    }

    Serial.printf("Bonus request failed: HTTP %d (attempt %u)\n", status, attempt + 1);
    http.end();
    // 4xx javobni takrorlash foydasiz (masalan, faol bonus yo'q).
    if (status >= 400 && status < 500) {
      setDisplay("MUKOFOT YO'Q", false);
      return;
    }
    delay(400U * (attempt + 1));
  }
  Serial.println("Bonus request failed after retries; no physical impulses emitted");
  setDisplay("ALOQA YO'Q", false);
}

void IRAM_ATTR onButtonPress() {
  const uint32_t now = micros();
  if (now - lastButtonInterruptAt < BUTTON_DEBOUNCE_MS * 1000U) return;
  lastButtonInterruptAt = now;
  if (pendingButtonPresses < 255) pendingButtonPresses++;
}

void pollButton() {
  noInterrupts();
  const uint8_t presses = pendingButtonPresses;
  pendingButtonPresses = 0;
  interrupts();

  for (uint8_t press = 0; press < presses; press++) {
    if (testModeActive) {
      Serial.println("Button press ignored while box test mode is active");
    } else {
      requestBonus();
    }
  }
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
  // Eng birinchi qadam: impuls chizig'ini aniq holatga keltirish.
  // Quvvat yonganda pin erkin qolsa, bill acceptor soxta impuls ko'rishi mumkin.
  pinMode(PULSE_OUTPUT_PIN, OUTPUT);
  setPulseIdle();

  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), onButtonPress, FALLING);
  WiFi.mode(WIFI_STA);

  panelConfig.gpio = panelPins;
  panelConfig.clkphase = false;
  panelConfig.double_buff = false;
  panel.begin();
  panel.setBrightness8(80);
  panel.clearScreen();

  connectWiFi();
  Serial.printf("Tomchi panel ready for %s\n", BOX_ID);
  Serial.printf("Pulse output pin %d ready; defaults: %s active, %u ms period\n",
                PULSE_OUTPUT_PIN,
                pulseActiveHigh ? "HIGH" : "LOW",
                static_cast<unsigned>(pulseFrequencyMs));
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
