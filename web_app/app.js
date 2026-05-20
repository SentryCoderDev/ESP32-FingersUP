// FingersUP Web Uygulamasi
const MQTT_BROKER = 'wss://broker.emqx.io:8084/mqtt';
const clientId = 'fingersup-web-' + Math.random().toString(16).substr(2, 8);

let client = null;
let connected = false;

// LED state tracking
let ledStates = { kirmizi: false, yesil: false, mavi: false };

// Log area
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

    // Map LED state to virtual finger command
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

// Connect on load
window.addEventListener('DOMContentLoaded', () => {
    addLog('SISTEM', 'Web uygulamasi baslatildi');
    connectMQTT();
});
