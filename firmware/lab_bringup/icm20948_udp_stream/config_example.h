#pragma once

// Copy this file to config.h and replace the local network values.
// config.h is ignored by git.
constexpr char WIFI_SSID[] = "YOUR_WIFI_SSID";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";
constexpr char BACKEND_HOST[] = "192.168.1.100";
constexpr uint16_t BACKEND_PORT = 9000;

// This physical node ID is joined to its UWB tag in responders.local.yaml.
constexpr char IMU_NODE_ID[] = "imu_waist_01";

constexpr int I2C_SDA_PIN = 21;
constexpr int I2C_SCL_PIN = 22;
// SparkFun breakout default: 1. Use 0 only when AD0 is pulled low.
constexpr bool ICM_AD0_VALUE = true;
constexpr uint16_t IMU_SAMPLE_RATE_HZ = 50;
