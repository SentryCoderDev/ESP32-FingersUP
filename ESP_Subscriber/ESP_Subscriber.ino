/*
 * FingersUP - ESP8266 Subscriber & Web Host
 *
 * PCB pinout (7-Segment Common Cathode):
 *   g=D1, f=D2, a=D3, b=D4, dp=D5, c=D6, d=D7, e=D8
 *   Common pins connected to GND via 220Ω resistors
 *
 * GOREVLER:
 *   - Local Web Server: index.html, style.css, app.js yayınlar.
 *   - WiFi + MQTT subscriber (fingersup/gesture ve fingersup/webcmd)
 *   - 7-segment display komut numarasini veya parmak sayisini gosterir
 *   - UART uzerinden Arduino'ya komut gonderir (temiz formatta)
 *   - Arduino'dan gelen sensör verilerini (JSON) okuyup fingersup/status kanalına yayınlar
 */

#include <ESP8266WiFi.h>
#define MQTT_MAX_PACKET_SIZE 512
#include <PubSubClient.h>
#include <ESP8266WebServer.h>

const char* ssid = "SentryBOT";
const char* password = "SentryBOT";

const char* mqttServer = "broker.emqx.io";
const int mqttPort = 1883;
const char* mqttTopic = "fingersup/gesture";
const char* mqttWebTopic = "fingersup/webcmd";
const char* mqttStatusTopic = "fingersup/status";

WiFiClient espClient;
PubSubClient client(espClient);
ESP8266WebServer server(80);

// 7-Segment: segPins[0..6] = {a,b,c,d,e,f,g}
const int segPins[7] = {D3, D4, D6, D7, D0, D2, D1};
const int dpPin = D5;

const byte digitPatterns[10][7] = {
  {1,1,1,1,1,1,0}, // 0
  {0,1,1,0,0,0,0}, // 1
  {1,1,0,1,1,0,1}, // 2
  {1,1,1,1,0,0,1}, // 3
  {0,1,1,0,0,1,1}, // 4
  {1,0,1,1,0,1,1}, // 5
  {1,0,1,1,1,1,1}, // 6
  {1,1,1,0,0,0,0}, // 7
  {1,1,1,1,1,1,1}, // 8
  {1,1,1,1,0,1,1}  // 9
};

unsigned long lastReconnectAttempt = 0;

// ── Web Sayfası İçerikleri (Embedded Web App) ────────────────────

const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FingersUP - Akilli Ev Kontrol</title>
    <script src="https://unpkg.com/mqtt/dist/mqtt.min.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>FingersUP Akilli Ev</h1>
            <div class="status-bar">
                <span id="connStatus" class="badge offline">BAGLANMADI</span>
                <span id="faceStatus" class="badge">Yuz: -</span>
            </div>
        </header>

        <div class="grid">
            <!-- LED Kontrol -->
            <div class="card">
                <h2>LED Kontrol</h2>
                <div class="led-group">
                    <button class="led-btn red" data-led="kirmizi" onclick="toggleLED('kirmizi')">Kirmizi</button>
                    <button class="led-btn green" data-led="yesil" onclick="toggleLED('yesil')">Yesil</button>
                    <button class="led-btn blue" data-led="mavi" onclick="toggleLED('mavi')">Mavi</button>
                </div>
                <div class="led-status">
                    <span id="ledKirmizi" class="led-indicator off">R</span>
                    <span id="ledYesil" class="led-indicator off">G</span>
                    <span id="ledMavi" class="led-indicator off">B</span>
                </div>
            </div>

            <!-- Sensorler -->
            <div class="card">
                <h2>Sensorler</h2>
                <div class="sensor">
                    <label>Sicaklik:</label>
                    <span id="sicaklik">--</span>
                </div>
                <div class="sensor">
                    <label>Isik (LDR):</label>
                    <span id="isik">--</span>
                </div>
                <div class="sensor">
                    <label>Kapi Mesafe:</label>
                    <span id="mesafe">--</span>
                </div>
                <div class="sensor">
                    <label>IR:</label>
                    <span id="irDurum">--</span>
                </div>
            </div>

            <!-- Servo Kontrol -->
            <div class="card">
                <h2>Servo Motor</h2>
                <div class="servo-control">
                    <input type="range" id="servoSlider" min="0" max="180" value="90"
                           oninput="servoControl(this.value)">
                    <span id="servoAci">90°</span>
                </div>
                <div class="servo-presets">
                    <button onclick="servoPreset(0)">0°</button>
                    <button onclick="servoPreset(45)">45°</button>
                    <button onclick="servoPreset(90)">90°</button>
                    <button onclick="servoPreset(135)">135°</button>
                    <button onclick="servoPreset(180)">180°</button>
                </div>
            </div>

            <!-- Sistem -->
            <div class="card">
                <h2>Sistem</h2>
                <div class="sys-controls">
                    <button class="sys-btn" onclick="sendCommand('SISTEM_DURUM')">Durum Bilgisi</button>
                    <button class="sys-btn danger" onclick="sendCommand('ALARM_AC')">Alarm Ac</button>
                    <button class="sys-btn" onclick="sendCommand('ALARM_KAPA')">Alarm Kapa</button>
                    <button class="sys-btn danger" onclick="sendCommand('BUZZER_TEST')">Buzzer Test</button>
                    <button class="sys-btn" onclick="sendCommand('YENIDEN_BASLAT')">Yeniden Baslat</button>
                </div>
            </div>

            <!-- Son Komut -->
            <div class="card full-width">
                <h2>Son Komutlar</h2>
                <div id="logArea" class="log"></div>
            </div>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>
)rawliteral";

const char STYLE_CSS[] PROGMEM = R"rawliteral(
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0f0f1a;
    color: #e0e0e0;
    min-height: 100vh;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 20px;
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border-radius: 12px;
    margin-bottom: 24px;
    border: 1px solid #2a2a4a;
}

header h1 {
    font-size: 1.5rem;
    background: linear-gradient(90deg, #00d4ff, #00ff88);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.status-bar {
    display: flex;
    gap: 12px;
    align-items: center;
}

.badge {
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    background: #2a2a4a;
    border: 1px solid #3a3a5a;
}

.badge.online {
    background: #003d1a;
    border-color: #00ff88;
    color: #00ff88;
}

.badge.offline {
    background: #3d0000;
    border-color: #ff4444;
    color: #ff4444;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 20px;
}

.card {
    background: #1a1a2e;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #2a2a4a;
}

.card h2 {
    font-size: 1.1rem;
    margin-bottom: 16px;
    color: #00d4ff;
    border-bottom: 1px solid #2a2a4a;
    padding-bottom: 8px;
}

.card.full-width {
    grid-column: 1 / -1;
}

.led-group {
    display: flex;
    gap: 10px;
    margin-bottom: 12px;
}

.led-btn {
    flex: 1;
    padding: 10px;
    border: 2px solid #3a3a5a;
    border-radius: 8px;
    background: #252540;
    color: #e0e0e0;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
}

.led-btn:hover {
    background: #303050;
}

.led-btn.red { border-color: #ff4444; }
.led-btn.red.active { background: #ff4444; color: #fff; box-shadow: 0 0 15px rgba(255, 68, 68, 0.4); }
.led-btn.green { border-color: #44ff44; }
.led-btn.green.active { background: #44ff44; color: #000; box-shadow: 0 0 15px rgba(68, 255, 68, 0.4); }
.led-btn.blue { border-color: #4444ff; }
.led-btn.blue.active { background: #4444ff; color: #fff; box-shadow: 0 0 15px rgba(68, 68, 255, 0.4); }

.led-status {
    display: flex;
    gap: 12px;
    justify-content: center;
}

.led-indicator {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 0.8rem;
    transition: all 0.3s;
}

.led-indicator.off {
    background: #1a1a2e;
    border: 2px solid #3a3a5a;
    color: #666;
}

.led-indicator.on {
    box-shadow: 0 0 20px rgba(255,255,255,0.3);
}

.led-indicator.on[data-color="kirmizi"] { background: #ff2222; border-color: #ff4444; }
.led-indicator.on[data-color="yesil"] { background: #22ff22; border-color: #44ff44; }
.led-indicator.on[data-color="mavi"] { background: #2222ff; border-color: #4444ff; }

.sensor {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #1f1f35;
}

.sensor label {
    color: #888;
}

.sensor span {
    font-weight: 600;
    color: #00ff88;
}

.servo-control {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}

.servo-control input[type="range"] {
    flex: 1;
    height: 6px;
    -webkit-appearance: none;
    appearance: none;
    background: linear-gradient(90deg, #00d4ff, #ff8800);
    border-radius: 3px;
    outline: none;
}

.servo-control input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #00d4ff;
    cursor: pointer;
    border: 2px solid #00ff88;
}

.servo-control span {
    font-size: 1.2rem;
    font-weight: bold;
    min-width: 50px;
    color: #ff8800;
}

.servo-presets {
    display: flex;
    gap: 8px;
}

.servo-presets button {
    flex: 1;
    padding: 6px;
    border: 1px solid #3a3a5a;
    border-radius: 6px;
    background: #252540;
    color: #e0e0e0;
    cursor: pointer;
    font-size: 0.8rem;
    transition: all 0.2s;
}

.servo-presets button:hover {
    background: #303050;
    border-color: #00d4ff;
}

.sys-controls {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.sys-btn {
    padding: 8px 16px;
    border: 1px solid #3a3a5a;
    border-radius: 8px;
    background: #252540;
    color: #e0e0e0;
    cursor: pointer;
    font-size: 0.85rem;
    transition: all 0.2s;
}

.sys-btn:hover {
    background: #303050;
    border-color: #00d4ff;
}

.sys-btn.danger {
    border-color: #ff4444;
    color: #ff6666;
}

.sys-btn.danger:hover {
    background: #3d0000;
}

.log {
    height: 150px;
    overflow-y: auto;
    font-family: 'Courier New', monospace;
    font-size: 0.8rem;
    padding: 10px;
    background: #0a0a15;
    border-radius: 8px;
    border: 1px solid #1f1f35;
}

.log-entry {
    padding: 4px 0;
    border-bottom: 1px solid #1a1a25;
    color: #aaa;
}

.log-entry .time {
    color: #666;
    margin-right: 8px;
}

.log-entry .cmd {
    color: #00d4ff;
}

@media (max-width: 768px) {
    .grid {
        grid-template-columns: 1fr;
    }
    header {
        flex-direction: column;
        gap: 12px;
        text-align: center;
    }
}
)rawliteral";

const char APP_JS[] PROGMEM = R"rawliteral(
const MQTT_BROKER = 'wss://broker.emqx.io:8084/mqtt';
const clientId = 'fingersup-web-' + Math.random().toString(16).substr(2, 8);

let client = null;
let connected = false;

let ledStates = { kirmizi: false, yesil: false, mavi: false };

const logArea = document.getElementById('logArea');

function addLog(cmd, detail) {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const now = new Date();
    const time = now.toLocaleTimeString('tr-TR');
    entry.innerHTML = `<span class="time">[${time}]</span><span class="cmd">${cmd}</span> ${detail || ''}`;
    logArea.appendChild(entry);
    logArea.scrollTop = logArea.scrollHeight;
}

function connectMQTT() {
    client = mqtt.connect(MQTT_BROKER, {
        clientId: clientId,
        clean: true
    });

    client.on('connect', () => {
        connected = true;
        document.getElementById('connStatus').textContent = 'BAGLANDI';
        document.getElementById('connStatus').className = 'badge online';
        addLog('MQTT', 'Broker\'a baglanildi');

        client.subscribe('fingersup/gesture');
        client.subscribe('fingersup/face');
        client.subscribe('fingersup/status');
    });

    client.on('message', (topic, message) => {
        const msg = message.toString();
        handleMessage(topic, msg);
    });

    client.on('error', (err) => {
        console.error('MQTT Error:', err);
        addLog('HATA', err.message);
    });

    client.on('close', () => {
        connected = false;
        document.getElementById('connStatus').textContent = 'BAGLANTI KOPTU';
        document.getElementById('connStatus').className = 'badge offline';
        addLog('MQTT', 'Baglanti koptu, yeniden deneniyor...');
        setTimeout(connectMQTT, 5000);
    });
}

function handleMessage(topic, msg) {
    switch (topic) {
        case 'fingersup/gesture':
            addLog('HAREKET', msg);
            updateFromGesture(msg);
            break;
        case 'fingersup/face':
            document.getElementById('faceStatus').textContent = 'Yuz: ' + msg;
            addLog('YÜZ', msg);
            break;
        case 'fingersup/status':
            try {
                const data = JSON.parse(msg);
                updateSensors(data);
            } catch {
                addLog('DURUM', msg);
            }
            break;
    }
}

function updateFromGesture(cmd) {
    if (cmd.startsWith('DIRECT_')) {
        const fingers = cmd.substring(7);
        if (fingers.length >= 3) {
            updateLEDUI('kirmizi', fingers[0] === '1');
            updateLEDUI('yesil', fingers[1] === '1');
            updateLEDUI('mavi', fingers[2] === '1');
        }
    } else if (cmd.startsWith('ANALOG_')) {
        const parts = cmd.split('_');
        if (parts.length >= 3) {
            const val = parseInt(parts[2]);
            if (!isNaN(val)) {
                document.getElementById('servoSlider').value = val;
                document.getElementById('servoAci').textContent = val + '\u00b0';
            }
        }
    } else if (cmd.startsWith('EXEC_')) {
        const parts = cmd.split('_');
        if (parts.length >= 3) {
            const menuNo = parseInt(parts[1]);
            const subNo = parseInt(parts[2]);
            if (menuNo === 1) { // Isiklar Menu
                if (subNo === 1) {
                    updateLEDUI('kirmizi', !ledStates.kirmizi);
                } else if (subNo === 2) {
                    updateLEDUI('yesil', !ledStates.yesil);
                } else if (subNo === 3) {
                    updateLEDUI('mavi', !ledStates.mavi);
                }
            }
        }
    }
}

function updateSensors(data) {
    if (data.sicaklik !== undefined) {
        document.getElementById('sicaklik').textContent = data.sicaklik.toFixed(1) + ' C';
    }
    if (data.isik !== undefined) {
        document.getElementById('isik').textContent = data.isik;
    }
    if (data.mesafe !== undefined) {
        document.getElementById('mesafe').textContent = data.mesafe + ' cm';
    }
    if (data.ir !== undefined) {
        document.getElementById('irDurum').textContent = data.ir ? 'Sinyal' : 'Beklemede';
    }
    if (data.ledler !== undefined) {
        const l = data.ledler;
        const rVal = (Number(l.r) === 1);
        const gVal = (Number(l.g) === 1);
        const bVal = (Number(l.b) === 1);
        
        if (rVal !== ledStates.kirmizi || gVal !== ledStates.yesil || bVal !== ledStates.mavi) {
            updateLEDUI('kirmizi', rVal);
            updateLEDUI('yesil', gVal);
            updateLEDUI('mavi', bVal);
            addLog('SISTEM', `LED Durumlari Guncellendi -> K:${rVal?'1':'0'} Y:${gVal?'1':'0'} M:${bVal?'1':'0'}`);
        }
    }
    if (data.servo !== undefined) {
        const sVal = parseInt(data.servo);
        const currentSliderVal = parseInt(document.getElementById('servoSlider').value);
        if (sVal !== currentSliderVal) {
            document.getElementById('servoSlider').value = sVal;
            document.getElementById('servoAci').textContent = sVal + '\u00b0';
            addLog('SISTEM', `Servo Guncellendi -> ${sVal}°`);
        }
    }
}

function updateLEDUI(renk, durum) {
    ledStates[renk] = durum;
    const el = document.getElementById('led' + renk.charAt(0).toUpperCase() + renk.slice(1));
    if (el) {
        el.className = 'led-indicator' + (durum ? ' on' : ' off');
        el.setAttribute('data-color', renk);
    }
    const btn = document.querySelector(`[data-led="${renk}"]`);
    if (btn) {
        if (durum) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    }
}

function toggleLED(renk) {
    if (!connected) return;
    ledStates[renk] = !ledStates[renk];
    updateLEDUI(renk, ledStates[renk]);

    const r = ledStates.kirmizi ? '1' : '0';
    const g = ledStates.yesil ? '1' : '0';
    const b = ledStates.mavi ? '1' : '0';
    const cmd = `WEB_LED_${r}${g}${b}`;
    client.publish('fingersup/webcmd', cmd);
    addLog('WEB', `LED ${renk} -> ${ledStates[renk] ? 'ACIK' : 'KAPALI'}`);
}

function servoControl(val) {
    document.getElementById('servoAci').textContent = val + '\u00b0';
    if (connected) {
        client.publish('fingersup/webcmd', `WEB_SERVO_${val}`);
        addLog('WEB', `Servo -> ${val}\u00b0`);
    }
}

function servoPreset(aci) {
    document.getElementById('servoSlider').value = aci;
    servoControl(aci);
}

function sendCommand(cmd) {
    if (!connected) return;
    client.publish('fingersup/webcmd', cmd);
    addLog('WEB', cmd);
}

window.addEventListener('DOMContentLoaded', () => {
    addLog('SISTEM', 'Web uygulamasi baslatildi');
    connectMQTT();
});
)rawliteral";

// ── Setup ve Diğer İşlemler ──────────────────────────────────────

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(50);
  Serial.println();
  Serial.println("FingersUP ESP8266 Basliyor...");

  for (int i = 0; i < 7; i++) {
    pinMode(segPins[i], OUTPUT);
    digitalWrite(segPins[i], HIGH);  // Kapat
  }

  pinMode(dpPin, OUTPUT);
  digitalWrite(dpPin, HIGH);

  // Boot animasyonu: 0'dan 9'a say
  for (int d = 0; d <= 9; d++) {
    showDigit(d);
    delay(100);
  }
  showDigit(0);

  // WiFi Bağlantısı
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("WiFi Baglaniliyor...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" Baglandi!");
  Serial.print("IP Adresi: ");
  Serial.println(WiFi.localIP());

  // Web Server Kurulumu
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/html", INDEX_HTML);
  });
  server.on("/style.css", HTTP_GET, []() {
    server.send(200, "text/css", STYLE_CSS);
  });
  server.on("/app.js", HTTP_GET, []() {
    server.send(200, "application/javascript", APP_JS);
  });
  server.begin();
  Serial.println("Web Server 80 portunda baslatildi!");

  // MQTT Kurulumu
  client.setServer(mqttServer, mqttPort);
  client.setCallback(callback);
}

void mqttReconnect() {
  Serial.print("MQTT baglaniliyor...");
  String clientId = "FingersUP-ESP-";
  clientId += String(ESP.getChipId());
  
  if (client.connect(clientId.c_str())) {
    Serial.println(" Baglandi!");
    client.subscribe(mqttTopic);
    client.subscribe(mqttWebTopic); // Web komutlarını da dinle
    client.publish(mqttStatusTopic, "{\"status\":\"online\"}");
    showDigit(0);
  } else {
    Serial.print(" Hata: ");
    Serial.println(client.state());
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  char msg[64];
  unsigned int len = length < 63 ? length : 63;
  memcpy(msg, payload, len);
  msg[len] = '\0';

  // Arduino'ya komutu temiz formatta ilet
  Serial.println(msg);

  updateSegmentFromCommand(msg);
}

void updateSegmentFromCommand(const char* cmd) {
  if (strcmp(cmd, "CONF") == 0 || strcmp(cmd, "CONF_EXIT") == 0 || strcmp(cmd, "MENU_TIMEOUT") == 0) {
    showDigit(0);
  } else if (strncmp(cmd, "FINGERS_", 8) == 0) {
    char c = cmd[8];
    if (c >= '0' && c <= '9') showDigit(c - '0');
  } else if (strncmp(cmd, "EXEC_", 5) == 0) {
    char c = cmd[strlen(cmd) - 1];
    if (c >= '0' && c <= '9') showDigit(c - '0');
  } else if (strncmp(cmd, "ANALOG_", 7) == 0) {
    char c = cmd[strlen(cmd) - 1];
    if (c >= '0' && c <= '9') showDigit(c - '0');
  } else if (strncmp(cmd, "DIRECT_", 7) == 0) {
    int count = 0;
    for (int i = 7; cmd[i] != '\0' && i < 12; i++) {
      if (cmd[i] == '1') count++;
    }
    showDigit(count);
  } else if (strncmp(cmd, "MENU_", 5) == 0) {
    const char* name = cmd + 5;

    if (name[0] >= '0' && name[0] <= '9') {
      showDigit(name[0] - '0');
    } else if (strcmp(name, "Isiklar") == 0) {
      showDigit(1);
    } else if (strcmp(name, "Sicaklik") == 0) {
      showDigit(2);
    } else if (strcmp(name, "Guvenlik") == 0) {
      showDigit(3);
    } else if (strcmp(name, "Perde") == 0) {
      showDigit(4);
    } else if (strcmp(name, "Sistem") == 0) {
      showDigit(5);
    }
  }
}

void showDigit(int num) {
  if (num < 0 || num > 9) num = 0;

  for (int i = 0; i < 7; i++) {
    // Ortak Katot (HIGH ile yanar) ise LOW->HIGH / HIGH->LOW yapabilirsiniz.
    // Mevcut kodunuzda anot mantığı çalışıyordu (LOW = aktif):
    digitalWrite(segPins[i], digitPatterns[num][i] ? LOW : HIGH);
  }

  digitalWrite(dpPin, HIGH);
}

void loop() {
  // MQTT Bağlantısı Kontrolü (Non-blocking)
  if (!client.connected()) {
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      mqttReconnect();
    }
  } else {
    client.loop();
  }

  // Web Server İstemcilerini Yönet
  server.handleClient();

  // Canlı teşhis için 3 saniyede bir heartbeat yayınla
  static unsigned long lastHeartbeat = 0;
  unsigned long currentMillis = millis();
  if (currentMillis - lastHeartbeat > 3000) {
    lastHeartbeat = currentMillis;
    if (client.connected()) {
      client.publish(mqttStatusTopic, "{\"status\":\"esp_online\"}");
    }
  }

  // Arduino'dan gelen seri port telemetry verilerini oku (Bridge Modu)
  if (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    int firstBrace = line.indexOf('{');
    int lastBrace = line.lastIndexOf('}');
    if (firstBrace != -1 && lastBrace != -1 && lastBrace > firstBrace) {
      String json = line.substring(firstBrace, lastBrace + 1);
      if (client.connected()) {
        client.publish(mqttStatusTopic, json.c_str());
      }
    } else if (line.length() > 0) {
      // JSON formatına uymayan hatayı/gürültüyü de MQTT'ye yolla (Teşhis için)
      String dbg = "{\"raw_debug\":\"" + line + "\"}";
      if (client.connected()) {
        client.publish(mqttStatusTopic, dbg.c_str());
      }
    }
  }
}
