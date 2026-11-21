#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <HX711_ADC.h>
#include <DHT.h>
#include <TM1637Display.h>

const char* ssid = "IOT";         
const char* password = "12345678"; 
const char* server_ip = "10.50.28.95"; 
const int server_port = 8080;

float CALIBRATION_FACTOR = 395.0; 

#define PIN_DS18B20 4    
#define PIN_DHT27   27   
#define DHTTYPE     DHT22

// Pin 7-Segment TM1637
#define CLK_PIN     22
#define DIO_PIN     21

// Pin Khusus I2C LCD
#define I2C_SDA     32
#define I2C_SCL     33

// Pin Loadcell
const int LC_DOUT_PIN = 19;
const int LC_SCK_PIN = 18;

// Pin Relay
#define PIN_RELAY_HEATER   23  
#define PIN_RELAY_MOTOR    26  
#define PIN_RELAY_FAN1     16 
#define PIN_RELAY_FAN2     25 
#define PIN_RELAY_FAN3     17  
#define PIN_RELAY_PENGADUK 13 

#define RELAY_ON  LOW
#define RELAY_OFF HIGH

OneWire oneWire(PIN_DS18B20);
DallasTemperature sensors(&oneWire);
HX711_ADC LoadCell(LC_DOUT_PIN, LC_SCK_PIN);
LiquidCrystal_I2C lcd(0x27, 16, 2); 
DHT dht(PIN_DHT27, DHTTYPE);
TM1637Display display(CLK_PIN, DIO_PIN);

enum SystemState { STATE_IDLE, STATE_GRINDING, STATE_DRYING, STATE_COOLING, STATE_TES_HEATER, STATE_TES_PENGADUK, STATE_TES_GRINDING, STATE_TES_COOLING };
SystemState currentState = STATE_IDLE;
String current_mode = "STANDBY";
String status_esp = "BOOT"; 

float suhu_kompor = 0.0, suhu_ruang = 0.0, current_weight = 0.0, current_humidity = 80.0; 
float t_suhu = 75.0; 
unsigned long t_waktu_target = 0, start_time = 0, motor_giling_duration = 10000;

// Variabel Global Interlock & Deadband Pengaduk
int stir_seq = 0; 
unsigned long seq_start = 0;

unsigned long previous_http_time = 0;
const long http_interval = 1000; 
unsigned long last_temp_request = 0;
const int temp_delay = 750; 
bool is_drying_temp_reached = false;
unsigned long drying_start_time = 0;
bool is_fan_overheat_active = false; 

unsigned long last_wifi_check = 0;
const unsigned long wifi_reconnect_interval = 5000; 

void matikanSemuaAktuator() {
  digitalWrite(PIN_RELAY_HEATER, RELAY_OFF); digitalWrite(PIN_RELAY_FAN1, RELAY_OFF);
  digitalWrite(PIN_RELAY_FAN2, RELAY_OFF); digitalWrite(PIN_RELAY_FAN3, RELAY_OFF);
  digitalWrite(PIN_RELAY_MOTOR, RELAY_OFF); digitalWrite(PIN_RELAY_PENGADUK, RELAY_OFF);
}

void selesaiProses() { 
    matikanSemuaAktuator(); currentState = STATE_IDLE; current_mode = "STANDBY"; 
    status_esp = "DONE"; 
}

String getFaseString() {
  switch (currentState) {
    case STATE_IDLE: return "IDLE"; case STATE_GRINDING: return "GRINDING";
    case STATE_DRYING: return "DRYING"; case STATE_COOLING: return "COOLING"; case STATE_TES_HEATER: return "TES_HEATER";
    case STATE_TES_PENGADUK: return "TES_PENGADUK"; case STATE_TES_GRINDING: return "TES_GRINDING"; case STATE_TES_COOLING: return "TES_COOLING";
  } return "IDLE";
}

String getFaseLcd() {
  switch (currentState) {
    case STATE_IDLE: return "STANDBY";
    case STATE_GRINDING: return "GRINDING";
    case STATE_DRYING: return "DRYING";
    case STATE_COOLING: return "COOLING";
    case STATE_TES_HEATER: return "T_HEATER";
    case STATE_TES_PENGADUK: return "T_STIRRER";
    case STATE_TES_GRINDING: return "T_CHOPPER";
    case STATE_TES_COOLING: return "T_FAN";
  }
  return "IDLE";
}

long getSisaWaktuDetik(unsigned long current_time) {
    if (currentState == STATE_IDLE) return 0;
    unsigned long elapsed = current_time - start_time;
    switch (currentState) {
        case STATE_GRINDING: return (motor_giling_duration > elapsed) ? (motor_giling_duration - elapsed)/1000 : 0;
        case STATE_DRYING: return (!is_drying_temp_reached) ? 0 : ((t_waktu_target > (current_time - drying_start_time)) ? (t_waktu_target - (current_time - drying_start_time))/1000 : 0);
        case STATE_COOLING:
        case STATE_TES_GRINDING:
        case STATE_TES_COOLING:
        case STATE_TES_HEATER:
        case STATE_TES_PENGADUK: return (t_waktu_target > elapsed) ? (t_waktu_target - elapsed)/1000 : 0;
        default: return 0;
    }
}

void updateSevenSegment(unsigned long current_time) {
  static unsigned long last_toggle = 0; static bool show_temp = true;
  if (current_time - last_toggle >= 2000) { show_temp = !show_temp; last_toggle = current_time; }
  if (show_temp || currentState == STATE_IDLE) { display.showNumberDecEx((int)(suhu_kompor * 10), 0b11100000, false, 4, 0); } 
  else { display.showNumberDec((int)getSisaWaktuDetik(current_time), true); }
}

void updateLCD(unsigned long current_time) {
  static unsigned long last_refresh = 0;
  static unsigned long last_toggle = 0;
  static bool toggle_view = false;

  if (current_time - last_toggle >= 2000) {
    last_toggle = current_time;
    toggle_view = !toggle_view;
  }

  if (current_time - last_refresh >= 500) {
    last_refresh = current_time;
    String l1;
    if (toggle_view) {
      l1 = "T:" + String(suhu_kompor, 1) + "C W:" + String((int)current_weight) + "g";
    } else {
      l1 = "H:" + String(current_humidity, 1) + "% W:" + String((int)current_weight) + "g";
    }
    while(l1.length() < 16) l1 += " "; 
    lcd.setCursor(0, 0);
    lcd.print(l1);

    String l2 = getFaseLcd();
    while(l2.length() < 10) l2 += " "; 
    long sisa = getSisaWaktuDetik(current_time);
    int m = sisa / 60;
    int s = sisa % 60;
    char timerStr[6];
    
    if (currentState == STATE_DRYING && !is_drying_temp_reached) {
        sprintf(timerStr, "HEAT "); 
    } else if (currentState == STATE_IDLE) {
        sprintf(timerStr, "00:00");
    } else {
        sprintf(timerStr, "%02d:%02d", m, s); 
    }
    
    l2 += String(timerStr);
    while(l2.length() < 16) l2 += " "; 
    lcd.setCursor(0, 1);
    lcd.print(l2);
  }
}

void setup() {
  Serial.begin(115200); 
  Wire.begin(I2C_SDA, I2C_SCL); 
  
  sensors.begin(); sensors.setWaitForConversion(false); sensors.requestTemperatures();
  dht.begin(); display.setBrightness(0x0f); display.clear();

  matikanSemuaAktuator();
  pinMode(PIN_RELAY_HEATER, OUTPUT); pinMode(PIN_RELAY_MOTOR, OUTPUT);
  pinMode(PIN_RELAY_FAN1, OUTPUT); pinMode(PIN_RELAY_FAN2, OUTPUT);
  pinMode(PIN_RELAY_FAN3, OUTPUT); pinMode(PIN_RELAY_PENGADUK, OUTPUT);

  lcd.init(); 
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("EcoSync Starting");
  
  LoadCell.begin(); LoadCell.start(2000, true); LoadCell.setCalFactor(CALIBRATION_FACTOR); 
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  lcd.clear(); 
}

void loop() {
  unsigned long current_time = millis();

  // Reconnect WiFi jika putus
  if (WiFi.status() != WL_CONNECTED) {
    if (current_time - last_wifi_check >= wifi_reconnect_interval) {
      WiFi.disconnect();
      WiFi.reconnect();
      last_wifi_check = current_time;
    }
  }

  if (LoadCell.update()) {
    float baca_sensor = LoadCell.getData();
    if (baca_sensor < 3.0 && baca_sensor > -5.0) { baca_sensor = 0.0; }
    static float berat_terkunci = 0.0;
    if (abs(baca_sensor - berat_terkunci) >= 3.0) { berat_terkunci = baca_sensor; }
    current_weight = max(0.0f, berat_terkunci);
  }

  if (current_time - last_temp_request >= temp_delay) {
    suhu_kompor = sensors.getTempCByIndex(0); sensors.requestTemperatures();             
    float t_env = dht.readTemperature(), h = dht.readHumidity();              
    if (!isnan(t_env)) suhu_ruang = t_env;
    if (!isnan(h)) current_humidity = h;
    last_temp_request = current_time;
  }
  
  updateSevenSegment(current_time);
  updateLCD(current_time);

  // KOMUNIKASI HTTP: Akan di-Bypass / di-Skip sementara jika motor pengaduk sedang menyala (stir_seq == 2)
  // Ini memastikan tidak ada antrean jaringan yang menyebabkan mikrokontroler hang/nge-lag saat motor harus segera dimatikan.
  if ((current_time - previous_http_time >= http_interval) && (WiFi.status() == WL_CONNECTED)) {
    if (currentState != STATE_DRYING || stir_seq != 2) {
      previous_http_time = current_time;
      HTTPClient http;
      http.setTimeout(1000); 
      
      String url = "http://" + String(server_ip) + ":" + String(server_port) + "/esp_update?";
      url += "suhu_kompor=" + String(suhu_kompor, 2) + "&suhu_ruang=" + String(suhu_ruang, 2) + "&lembab=" + String(current_humidity, 2) + "&berat=" + String((int)current_weight); 
      url += "&status=" + status_esp + "&fase_esp=" + getFaseString();
      url += "&sisa_wkt=" + String(getSisaWaktuDetik(current_time));
      url += "&tr=" + String(is_drying_temp_reached ? "1" : "0");
      url += "&ovh=" + String(is_fan_overheat_active ? "1" : "0");

      http.begin(url);
      if (http.GET() > 0) {
        String payload = http.getString();
        if (status_esp == "BOOT") { status_esp = "RUNNING"; }
        
        DynamicJsonDocument doc(384);
        if (!deserializeJson(doc, payload)) {
          if (doc["tare"]) LoadCell.tareNoDelay();

          String fase_server = doc["fase"]; 
          current_mode = doc["mode"].as<String>(); 
          
          if (fase_server == "IDLE" && currentState != STATE_IDLE) { selesaiProses(); } 
          else if (fase_server == "IDLE" && status_esp == "DONE") { status_esp = "RUNNING"; }
          
          if (status_esp == "RUNNING") { 
            if (fase_server == "GRINDING" && currentState == STATE_IDLE) {
                if (doc.containsKey("t_grinding")) { motor_giling_duration = (unsigned long)doc["t_grinding"] * 1000UL; } 
                else { motor_giling_duration = 10000UL; }
                matikanSemuaAktuator(); currentState = STATE_GRINDING; start_time = current_time; lcd.clear();
            }
            else if (fase_server == "DRYING" && currentState == STATE_IDLE) { 
                t_suhu = doc["t_suhu"]; 
                t_waktu_target = (unsigned long)doc["t_waktu"] * 1000UL;
                matikanSemuaAktuator(); 
                
                stir_seq = 0;
                seq_start = current_time; // Mulai hitung 40 detik awal

                currentState = STATE_DRYING; 
                start_time = current_time; 
                is_drying_temp_reached = false; 
                is_fan_overheat_active = false;
                lcd.clear(); 
            }
            else if (fase_server == "TES_GRINDING" && currentState == STATE_IDLE) { currentState = STATE_TES_GRINDING; t_waktu_target = (unsigned long)doc["t_waktu"] * 1000; start_time = current_time; lcd.clear(); }
            else if (fase_server == "TES_COOLING" && currentState == STATE_IDLE) { currentState = STATE_TES_COOLING; t_waktu_target = (unsigned long)doc["t_waktu"] * 1000; start_time = current_time; lcd.clear(); }
            else if (fase_server == "TES_HEATER" && currentState == STATE_IDLE) { currentState = STATE_TES_HEATER; t_waktu_target = (unsigned long)doc["t_waktu"] * 1000; start_time = current_time; lcd.clear(); }
            else if (fase_server == "TES_PENGADUK" && currentState == STATE_IDLE) { currentState = STATE_TES_PENGADUK; t_waktu_target = (unsigned long)doc["t_waktu"] * 1000; start_time = current_time; lcd.clear(); }
          }
        }
      } http.end();
    }
  }

  if (suhu_kompor >= 100.0 && currentState == STATE_DRYING) selesaiProses(); 
  
  unsigned long elapsed = current_time - start_time;

  switch (currentState) {
    case STATE_IDLE: 
      matikanSemuaAktuator(); 
      break;
      
    case STATE_GRINDING:
      digitalWrite(PIN_RELAY_MOTOR, RELAY_ON);
      if (elapsed >= motor_giling_duration) { selesaiProses(); } 
      break;
      
    case STATE_DRYING: 
      {
        if (suhu_kompor >= (t_suhu + 10.0)) is_fan_overheat_active = true; 
        else if (suhu_kompor <= t_suhu) is_fan_overheat_active = false; 
        
        if (is_fan_overheat_active) digitalWrite(PIN_RELAY_FAN3, RELAY_ON);
        else digitalWrite(PIN_RELAY_FAN3, RELAY_OFF);

        static bool heater_active = true;
        if (suhu_kompor >= t_suhu) {
            heater_active = false; 
            if (!is_drying_temp_reached) {
                is_drying_temp_reached = true; 
                drying_start_time = current_time; 
            }
        } else if (suhu_kompor <= (t_suhu - 5.0)) { 
            heater_active = true; 
        }

        // =========================================================================
        // SIKLUS 4 FASE (HEATER 40s -> MATI 3s -> MOTOR 3s -> MATI 3s)
        // =========================================================================
        bool allow_heater = true;

        if (stir_seq == 0) { 
            // FASE 0: WAKTU UNTUK HEATER BEKERJA NORMAL (40 DETIK)
            allow_heater = true; 
            digitalWrite(PIN_RELAY_PENGADUK, RELAY_OFF);
            if (current_time - seq_start >= 40000) {
                stir_seq = 1; 
                seq_start = current_time;
            }
        }
        else if (stir_seq == 1) { 
            // FASE 1: HEATER DIPAKSA MATI, TUNGGU JEDA 3 DETIK
            allow_heater = false; 
            digitalWrite(PIN_RELAY_PENGADUK, RELAY_OFF);
            if (current_time - seq_start >= 3000) {
                stir_seq = 2;
                seq_start = current_time;
            }
        } 
        else if (stir_seq == 2) { 
            // FASE 2: PENGADUK NYALA SELAMA 3 DETIK
            allow_heater = false;
            
            // CUT-OFF PAKSA TEPAT 3 DETIK (Tanpa peduli status wifi)
            if (current_time - seq_start >= 3000) {
                digitalWrite(PIN_RELAY_PENGADUK, RELAY_OFF); 
                stir_seq = 3;
                seq_start = current_time;
            } else {
                digitalWrite(PIN_RELAY_PENGADUK, RELAY_ON);
            }
        } 
        else if (stir_seq == 3) { 
            // FASE 3: PENGADUK MATI, TUNGGU JEDA 3 DETIK
            allow_heater = false;
            digitalWrite(PIN_RELAY_PENGADUK, RELAY_OFF);
            if (current_time - seq_start >= 3000) {
                stir_seq = 0; 
                seq_start = current_time; 
            }
        }
        
        // EKSEKUSI HEATER (Hanya jika diizinkan oleh allow_heater di atas)
        if (allow_heater && heater_active && !is_fan_overheat_active) {
            if (is_drying_temp_reached) {
                if ((current_time / 2000) % 2 == 0) digitalWrite(PIN_RELAY_HEATER, RELAY_ON);
                else digitalWrite(PIN_RELAY_HEATER, RELAY_OFF);
            } else {
                digitalWrite(PIN_RELAY_HEATER, RELAY_ON);
            }
        } else {
            digitalWrite(PIN_RELAY_HEATER, RELAY_OFF);
        }
        
        // CEK WAKTU SELESAI
        if (is_drying_temp_reached) { 
            if (current_time - drying_start_time >= t_waktu_target) { 
                matikanSemuaAktuator(); 
                currentState = STATE_COOLING; 
                start_time = current_time; 
                t_waktu_target = 180000; 
            } 
        }
      } break;
      
    case STATE_COOLING:
      digitalWrite(PIN_RELAY_FAN1, RELAY_ON); digitalWrite(PIN_RELAY_FAN2, RELAY_ON); digitalWrite(PIN_RELAY_FAN3, RELAY_ON);
      if (suhu_kompor <= 35.0 || elapsed >= t_waktu_target) selesaiProses();
      break;
      
    case STATE_TES_GRINDING: 
      digitalWrite(PIN_RELAY_MOTOR, RELAY_ON); if (elapsed >= t_waktu_target) selesaiProses(); break;
    case STATE_TES_COOLING:
      digitalWrite(PIN_RELAY_FAN1, RELAY_ON); digitalWrite(PIN_RELAY_FAN2, RELAY_ON); digitalWrite(PIN_RELAY_FAN3, RELAY_ON); if (elapsed >= t_waktu_target) selesaiProses(); break;
    case STATE_TES_HEATER: 
      digitalWrite(PIN_RELAY_HEATER, RELAY_ON); if (elapsed >= t_waktu_target) selesaiProses(); break;
    case STATE_TES_PENGADUK: 
      digitalWrite(PIN_RELAY_PENGADUK, RELAY_ON); 
      // Manual test disamakan maksimal nyala 3 detik
      if (elapsed >= 3000 || elapsed >= t_waktu_target) selesaiProses(); 
      break;
  }
}