#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <esp_timer.h>
#include "ICM_20948.h"

#include "config.h"

namespace {
constexpr float kStandardGravityMps2 = 9.80665F;
constexpr float kDegreesToRadians = 0.017453292519943295F;
constexpr uint32_t kSerialBaud = 115200;
constexpr size_t kPacketCapacity = 384;

ICM_20948_I2C imu;
WiFiUDP udp;
uint64_t sequenceNumber = 0;
uint32_t packetsThisSecond = 0;
uint32_t sendFailuresThisSecond = 0;
uint32_t lastRateReportMs = 0;
int64_t nextSampleUs = 0;

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  Serial.print("ESP32 address: ");
  Serial.println(WiFi.localIP());
}

void connectImu() {
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(400000);

  while (true) {
    imu.begin(Wire, ICM_AD0_VALUE ? 1 : 0);
    if (imu.status == ICM_20948_Stat_Ok) {
      break;
    }
    Serial.print("ICM-20948 initialization failed: ");
    Serial.println(imu.statusString());
    delay(500);
  }

  imu.swReset();
  delay(250);
  imu.sleep(false);
  imu.lowPower(false);
  imu.setSampleMode(
      ICM_20948_Internal_Acc | ICM_20948_Internal_Gyr,
      ICM_20948_Sample_Mode_Continuous);

  ICM_20948_fss_t fullScale;
  fullScale.a = gpm4;
  fullScale.g = dps500;
  imu.setFullScale(ICM_20948_Internal_Acc | ICM_20948_Internal_Gyr, fullScale);

  ICM_20948_dlpcfg_t filter;
  filter.a = acc_d50bw4_n68bw8;
  filter.g = gyr_d51bw2_n73bw3;
  imu.setDLPFcfg(ICM_20948_Internal_Acc | ICM_20948_Internal_Gyr, filter);
  const ICM_20948_Status_e accelFilter =
      imu.enableDLPF(ICM_20948_Internal_Acc, true);
  const ICM_20948_Status_e gyroFilter =
      imu.enableDLPF(ICM_20948_Internal_Gyr, true);
  if (accelFilter != ICM_20948_Stat_Ok || gyroFilter != ICM_20948_Stat_Ok) {
    Serial.println("ICM-20948 filter configuration failed; stopping.");
    while (true) {
      delay(1000);
    }
  }
  Serial.println("ICM-20948 ready");
}

bool sendMeasurement(int64_t timestampUs) {
  // SparkFun returns acceleration in mg and angular velocity in degrees/second.
  const float ax = imu.accX() * kStandardGravityMps2 / 1000.0F;
  const float ay = imu.accY() * kStandardGravityMps2 / 1000.0F;
  const float az = imu.accZ() * kStandardGravityMps2 / 1000.0F;
  const float gx = imu.gyrX() * kDegreesToRadians;
  const float gy = imu.gyrY() * kDegreesToRadians;
  const float gz = imu.gyrZ() * kDegreesToRadians;

  char packet[kPacketCapacity];
  const int length = snprintf(
      packet,
      sizeof(packet),
      "{\"version\":1,\"node_id\":\"%s\",\"sequence_number\":%llu,"
      "\"timestamp_us\":%lld,\"type\":\"imu\",\"data\":{"
      "\"ax_mps2\":%.6f,\"ay_mps2\":%.6f,\"az_mps2\":%.6f,"
      "\"gx_radps\":%.6f,\"gy_radps\":%.6f,\"gz_radps\":%.6f}}",
      IMU_NODE_ID,
      static_cast<unsigned long long>(sequenceNumber),
      static_cast<long long>(timestampUs),
      ax,
      ay,
      az,
      gx,
      gy,
      gz);
  if (length <= 0 || static_cast<size_t>(length) >= sizeof(packet)) {
    return false;
  }

  if (!udp.beginPacket(BACKEND_HOST, BACKEND_PORT)) {
    return false;
  }
  const size_t written = udp.write(
      reinterpret_cast<const uint8_t *>(packet), static_cast<size_t>(length));
  if (written != static_cast<size_t>(length) || !udp.endPacket()) {
    return false;
  }
  ++sequenceNumber;
  return true;
}

void reportRate() {
  const uint32_t nowMs = millis();
  if (nowMs - lastRateReportMs < 1000) {
    return;
  }
  Serial.printf(
      "imu packets/s=%lu send_failures/s=%lu wifi_rssi_dbm=%ld\n",
      static_cast<unsigned long>(packetsThisSecond),
      static_cast<unsigned long>(sendFailuresThisSecond),
      static_cast<long>(WiFi.RSSI()));
  packetsThisSecond = 0;
  sendFailuresThisSecond = 0;
  lastRateReportMs = nowMs;
}
}  // namespace

void setup() {
  static_assert(IMU_SAMPLE_RATE_HZ >= 50 && IMU_SAMPLE_RATE_HZ <= 100);
  Serial.begin(kSerialBaud);
  delay(500);
  connectWifi();
  connectImu();
  nextSampleUs = esp_timer_get_time();
  lastRateReportMs = millis();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }

  const int64_t nowUs = esp_timer_get_time();
  const int64_t intervalUs = 1000000LL / IMU_SAMPLE_RATE_HZ;
  if (nowUs < nextSampleUs) {
    reportRate();
    delay(1);
    return;
  }
  nextSampleUs += intervalUs;
  if (nowUs - nextSampleUs > intervalUs) {
    nextSampleUs = nowUs + intervalUs;
  }

  if (imu.dataReady()) {
    imu.getAGMT();
    if (sendMeasurement(nowUs)) {
      ++packetsThisSecond;
    } else {
      ++sendFailuresThisSecond;
    }
  }
  reportRate();
}
