#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

#define ONBOARD_LED 8
#define BOOT_BUTTON_PIN 9

const char *ssid = "BMONI_OFFLINE_NODE";
const char *password = "bmoni1234";

WebServer server(80);

String lastTransactionPayload = "No transaction recorded yet.";

// Temporary memory to hold values typed in the webpage inputs
String tempSender = "08012345678";
String tempReceiver = "09087654321";
double tempAmount = 1000.00;

// Debounce state variables for the BOOT button
int lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
unsigned long debounceDelay = 80; // 80ms debounce window

// Helper function to send transaction payload over Serial
void send_payload(String sender, String receiver, double amount) {
    // Flash onboard LED (Active LOW: LOW = ON)
    digitalWrite(ONBOARD_LED, LOW);
    delay(150);
    digitalWrite(ONBOARD_LED, HIGH);

    StaticJsonDocument<256> doc;
    doc["node_id"] = "C3_SUPERMINI_NODE_01";
    doc["sender_wallet"] = sender;
    doc["receiver_wallet"] = receiver;
    doc["amount"] = amount;
    doc["timestamp"] = millis();
    doc["status"] = "PENDING_LOCAL_SYNC";

    String jsonPayload;
    serializeJson(doc, jsonPayload);

    lastTransactionPayload = jsonPayload;

    // Send payload over USB Serial to Python Bridge
    Serial.print("PAYLOAD:");
    Serial.println(jsonPayload);
}

// Handler for the Root Dashboard (192.168.4.1)
void handleRoot() {
    String html = "<!DOCTYPE html><html><head><title>BMONI Mobile Terminal</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>";
    html += "body{font-family:Arial,sans-serif;text-align:center;padding:20px;background:#0d1117;color:#fff;}";
    html += ".card{background:#161b22;padding:20px;border-radius:10px;border:1px solid #30363d;margin-top:15px;text-align:left;}";
    html += "input{width:90%;padding:10px;margin:8px 0;border-radius:5px;border:1px solid #30363d;background:#0d1117;color:#fff;}";
    html += ".payload{word-wrap:break-word;font-family:monospace;color:#58a6ff;background:#010409;padding:10px;border-radius:5px;}";
    html += ".status{color:#10b981;font-weight:bold;font-size:0.9rem;margin-top:5px;}";
    html += "</style></head><body>";
    
    html += "<h2>BMONI Offline Terminal</h2>";
    html += "<p>Node: <strong>C3_SUPERMINI_NODE_01</strong></p>";
    html += "<p style='font-size:0.9rem;color:#8b949e;'>Fill in details below, then press the physical BOOT button on your ESP32 board to trigger payment!</p>";

    // Input Form
    html += "<div class='card'><h3>New Escrow Payment</h3>";
    html += "<label>Sender Wallet (Phone):</label><br>";
    html += "<input type='text' id='sender' value='" + tempSender + "' oninput='updateESP32()'><br>";
    html += "<label>Receiver Wallet (Phone):</label><br>";
    html += "<input type='text' id='receiver' value='" + tempReceiver + "' oninput='updateESP32()'><br>";
    html += "<label>Amount (NGN):</label><br>";
    html += "<input type='number' step='0.01' id='amount' value='" + String(tempAmount, 2) + "' oninput='updateESP32()'><br>";
    html += "<div class='status' id='status-indicator'>Syncing inputs with ESP32...</div>";
    html += "</div>";

    // Latest Transaction Display Card
    html += "<div class='card'><h3>Latest Logged Payload</h3>";
    html += "<div class='payload' id='payload-box'>" + lastTransactionPayload + "</div></div>";

    // JavaScript to push browser input changes to ESP32 memory in real-time
    html += "<script>";
    html += "function updateESP32() {";
    html += "  const s = document.getElementById('sender').value;";
    html += "  const r = document.getElementById('receiver').value;";
    html += "  const a = document.getElementById('amount').value;";
    html += "  document.getElementById('status-indicator').textContent = 'Updating...';";
    html += "  fetch('/update-fields?sender=' + encodeURIComponent(s) + '&receiver=' + encodeURIComponent(r) + '&amount=' + encodeURIComponent(a))";
    html += "    .then(response => {";
    html += "      if (response.ok) {";
    html += "        document.getElementById('status-indicator').textContent = 'Inputs synced to board memory!';";
    html += "      }";
    html += "    });";
    html += "}";
    html += "updateESP32();"; // Sync initial values
    
    // Poll the latest payload every 2 seconds to show what got logged when the physical button is pressed
    html += "setInterval(() => {";
    html += "  fetch('/get-payload').then(r => r.text()).then(t => {";
    html += "    document.getElementById('payload-box').textContent = t;";
    html += "  });";
    html += "}, 2000);";
    html += "</script>";

    html += "</body></html>";
    server.send(200, "text/html", html);
}

// Background endpoint to sync typed fields into ESP32 memory
void handleUpdateFields() {
    if (server.hasArg("sender")) tempSender = server.arg("sender");
    if (server.hasArg("receiver")) tempReceiver = server.arg("receiver");
    if (server.hasArg("amount")) tempAmount = server.arg("amount").toDouble();
    server.send(200, "text/plain", "OK");
}

// Background endpoint to let webpage fetch the latest payload
void handleGetPayload() {
    server.send(200, "text/plain", lastTransactionPayload);
}

void setup() {
    Serial.begin(115200);

    pinMode(ONBOARD_LED, OUTPUT);
    digitalWrite(ONBOARD_LED, HIGH); // Active LOW: HIGH = OFF

    // Set up BOOT button as input with pullup
    pinMode(BOOT_BUTTON_PIN, INPUT_PULLUP);

    // Set up ESP32 Access Point
    WiFi.softAP(ssid, password);

    server.on("/", handleRoot);
    server.on("/update-fields", HTTP_GET, handleUpdateFields);
    server.on("/get-payload", HTTP_GET, handleGetPayload);
    server.begin();

    delay(1000);
    Serial.println("==============================================");
    Serial.println(" BMONI MOBILE TERMINAL READY                 ");
    Serial.println(" AP: BMONI_OFFLINE_NODE (192.168.4.1)        ");
    Serial.println("==============================================");
}

void loop() {
    server.handleClient();

    // Check physical BOOT button pin state
    int buttonReading = digitalRead(BOOT_BUTTON_PIN);
    
    // Check if the button state changed
    if (buttonReading == LOW && lastButtonState == HIGH) {
        // Simple debounce: check if enough time has passed since last change
        if ((millis() - lastDebounceTime) > debounceDelay) {
            Serial.println("DEBUG: Physical BOOT button pressed!");
            // Send transaction payload using the values saved in memory
            send_payload(tempSender, tempReceiver, tempAmount);
            lastDebounceTime = millis();
        }
    }
    lastButtonState = buttonReading;
}