#include "esp_camera.h"
#include <HTTPClient.h>
#include <limits.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

// Configure these values for each wash box before flashing.
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_URL = "http://192.168.1.50:8000";
const char* DEVICE_KEY = "CHANGE_ME";
const char* BOX_ID = "box-1";
const char* SERVER_ROOT_CA = "";

constexpr int PIR_PIN = 13;
constexpr uint8_t FRAME_COUNT = 3;
constexpr uint32_t CAPTURE_INTERVAL_MS = 400;
constexpr uint32_t MOTION_COOLDOWN_MS = 5000;
constexpr uint32_t LIVE_FRAME_INTERVAL_MS = 1500;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr size_t MAX_JPEG_SIZE = 1024 * 1024;

// AI Thinker ESP32-CAM pin map. GPIO13 is available when the SD card is not used.
static camera_config_t cameraConfig = {
    .pin_pwdn = 32,
    .pin_reset = -1,
    .pin_xclk = 0,
    .pin_sccb_sda = 26,
    .pin_sccb_scl = 27,
    .pin_d7 = 35,
    .pin_d6 = 34,
    .pin_d5 = 39,
    .pin_d4 = 36,
    .pin_d3 = 21,
    .pin_d2 = 19,
    .pin_d1 = 18,
    .pin_d0 = 5,
    .pin_vsync = 25,
    .pin_href = 23,
    .pin_pclk = 22,
    .xclk_freq_hz = 20000000,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = PIXFORMAT_JPEG,
    .frame_size = FRAMESIZE_SVGA,
    .jpeg_quality = 10,
    .fb_count = 1,
    .fb_location = CAMERA_FB_IN_PSRAM,
    .grab_mode = CAMERA_GRAB_LATEST,
};

uint32_t lastMotionSentAt = 0;
uint32_t lastLiveFrameAt = 0;
uint32_t lastWiFiAttemptAt = 0;
bool wifiAttempted = false;
WiFiClient plainClient;
WiFiClientSecure secureClient;

bool beginHttp(HTTPClient& http, const String& url) {
  if (url.startsWith("https://")) {
    if (SERVER_ROOT_CA[0] == '\0') {
      Serial.println("Set SERVER_ROOT_CA before using HTTPS");
      return false;
    }
    secureClient.setCACert(SERVER_ROOT_CA);
    return http.begin(secureClient, url);
  }
  return http.begin(plainClient, url);
}

bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  const uint32_t now = millis();
  if (wifiAttempted && now - lastWiFiAttemptAt < WIFI_RETRY_MS) return false;
  lastWiFiAttemptAt = now;
  wifiAttempted = true;
  Serial.printf("Connecting to Wi-Fi for %s...\n", BOX_ID);
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  return false;
}

bool sendFrame(camera_fb_t* frame, uint8_t frameIndex, const String& eventId) {
  if (frame == nullptr || frame->format != PIXFORMAT_JPEG || frame->len == 0) {
    Serial.println("Camera returned an empty or non-JPEG frame");
    return false;
  }
  if (frame->len > MAX_JPEG_SIZE) {
    Serial.printf("JPEG too large: %u bytes\n", static_cast<unsigned>(frame->len));
    return false;
  }
  if (!connectWiFi()) return false;

  HTTPClient http;
  const String url = String(SERVER_URL) + "/api/detect-image";
  if (!beginHttp(http, url)) {
    Serial.println("Could not initialize HTTP client");
    return false;
  }

  const String boundary = "TomchiBoundary7MA4YWxkTrZu0gW";
  const String prefix =
      "--" + boundary + "\r\n"
      "Content-Disposition: form-data; name=\"image\"; filename=\"frame.jpg\"\r\n"
      "Content-Type: image/jpeg\r\n\r\n";
  const String suffix =
      "\r\n--" + boundary + "\r\n"
      "Content-Disposition: form-data; name=\"frame_index\"\r\n\r\n" +
      String(frameIndex) + "\r\n--" + boundary + "\r\n"
      "Content-Disposition: form-data; name=\"frame_count\"\r\n\r\n" +
      String(FRAME_COUNT) + "\r\n--" + boundary + "\r\n"
      "Content-Disposition: form-data; name=\"event_id\"\r\n\r\n" +
      eventId + "\r\n--" + boundary + "--\r\n";

  const size_t contentLength = prefix.length() + frame->len + suffix.length();
  if (contentLength > static_cast<size_t>(INT_MAX)) {
    http.end();
    Serial.println("Multipart request is too large");
    return false;
  }

  http.setTimeout(8000);
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  http.addHeader("X-Device-Key", DEVICE_KEY);
  http.addHeader("X-Box-Id", BOX_ID);
  http.addHeader("X-Frame-Count", String(FRAME_COUNT));

  // Build one multipart JPEG request in PSRAM when available.
  uint8_t* body = static_cast<uint8_t*>(ps_malloc(contentLength));
  if (body == nullptr) body = static_cast<uint8_t*>(malloc(contentLength));
  if (body == nullptr) {
    http.end();
    Serial.println("Not enough memory to prepare JPEG upload");
    return false;
  }

  size_t offset = 0;
  memcpy(body + offset, prefix.c_str(), prefix.length());
  offset += prefix.length();
  memcpy(body + offset, frame->buf, frame->len);
  offset += frame->len;
  memcpy(body + offset, suffix.c_str(), suffix.length());

  const int status = http.POST(body, contentLength);
  free(body);
  if (status < 200 || status >= 300) {
    Serial.printf("Image upload failed, HTTP %d\n", status);
    if (status > 0) Serial.println(http.getString());
    http.end();
    return false;
  }

  Serial.printf("Event %s frame %u/%u uploaded: %u bytes; %s\n",
                eventId.c_str(),
                frameIndex + 1, FRAME_COUNT, static_cast<unsigned>(frame->len),
                http.getString().c_str());
  http.end();
  return true;
}

bool initializeCamera() {
  const esp_err_t result = esp_camera_init(&cameraConfig);
  if (result != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", result);
    return false;
  }

  sensor_t* sensor = esp_camera_sensor_get();
  if (sensor != nullptr) {
    sensor->set_brightness(sensor, 0);
    sensor->set_contrast(sensor, 1);
    sensor->set_saturation(sensor, 0);
  }
  return true;
}

void captureAndUploadFrames() {
  const uint64_t mac = ESP.getEfuseMac();
  const String eventId =
      String(static_cast<uint32_t>(mac >> 32), HEX) +
      String(static_cast<uint32_t>(mac), HEX) + "-" +
      String(millis(), HEX) + "-" +
      String(esp_random(), HEX);

  for (uint8_t index = 0; index < FRAME_COUNT; index++) {
    camera_fb_t* frame = esp_camera_fb_get();
    if (frame == nullptr) {
      Serial.println("Failed to capture frame");
      continue;
    }

    sendFrame(frame, index, eventId);
    esp_camera_fb_return(frame);
    if (index + 1 < FRAME_COUNT) delay(CAPTURE_INTERVAL_MS);
  }
}

void uploadLiveFrame() {
  if (!connectWiFi()) return;

  sensor_t* sensor = esp_camera_sensor_get();
  if (sensor == nullptr || sensor->set_framesize(sensor, FRAMESIZE_QVGA) != 0) {
    Serial.println("Could not switch camera to live-preview resolution");
    return;
  }

  camera_fb_t* frame = esp_camera_fb_get();
  if (frame == nullptr) {
    sensor->set_framesize(sensor, FRAMESIZE_SVGA);
    Serial.println("Could not capture live-preview frame");
    return;
  }

  HTTPClient http;
  const String url = String(SERVER_URL) + "/api/boxes/" + BOX_ID + "/live-frame";
  if (beginHttp(http, url)) {
    http.addHeader("Content-Type", "image/jpeg");
    const int status = http.POST(frame->buf, frame->len);
    if (status < 200 || status >= 300) {
      Serial.printf("Live preview upload failed: HTTP %d\n", status);
    }
    http.end();
  }

  esp_camera_fb_return(frame);
  sensor->set_framesize(sensor, FRAMESIZE_SVGA);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIR_PIN, INPUT);
  WiFi.mode(WIFI_STA);

  if (!psramFound()) {
    Serial.println("PSRAM not detected; lower frame size or use an ESP32-CAM with PSRAM");
  }
  if (!initializeCamera()) {
    Serial.println("Camera unavailable; restarting in 5 seconds");
    delay(5000);
    ESP.restart();
  }

  connectWiFi();
  Serial.printf("Tomchi camera ready for %s\n", BOX_ID);
}

void loop() {
  connectWiFi();

  const uint32_t now = millis();
  if (digitalRead(PIR_PIN) == HIGH && now - lastMotionSentAt >= MOTION_COOLDOWN_MS) {
    lastMotionSentAt = now;
    Serial.printf("Motion detected at %s; capturing %u frames\n", BOX_ID, FRAME_COUNT);
    captureAndUploadFrames();
  }

  if (WiFi.status() == WL_CONNECTED &&
      millis() - lastLiveFrameAt >= LIVE_FRAME_INTERVAL_MS) {
    lastLiveFrameAt = millis();
    uploadLiveFrame();
  }

  delay(50);
}
