#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

#define ONBOARD_LED 8

const char *ssid = "BMONI_OFFLINE_NODE";
const char *password = "bmoni1234";

WebServer server(80);

String lastTransactionPayload = "No transaction recorded yet.";

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
    html += ".btn{background:#238636;color:white;padding:12px 20px;border:none;border-radius:5px;font-size:16px;width:100%;cursor:pointer;margin-top:10px;}";
    html += ".payload{word-wrap:break-word;font-family:monospace;color:#58a6ff;background:#010409;padding:10px;border-radius:5px;}";
    html += "</style></head><body>";
    
    html += "<h2>BMONI Offline Terminal</h2>";
    html += "<p>Node: <strong>C3_SUPERMINI_NODE_01</strong></p>";

    // Input Form for Custom Payments
    html += "<div class='card'><h3>New Escrow Payment</h3>";
    html += "<form action='/pay' method='POST'>";
    html += "<label>Sender Wallet (Phone):</label><br>";
    html += "<input type='text' name='sender' value='08012345678' required><br>";
    html += "<label>Receiver Wallet (Phone):</label><br>";
    html += "<input type='text' name='receiver' value='09087654321' required><br>";
    html += "<label>Amount (NGN):</label><br>";
    html += "<input type='number' step='0.01' name='amount' value='1000.00' required><br>";
    html += "<input type='submit' class='btn' value='Authorize & Send'>";
    html += "</form></div>";

    // Latest Transaction Display Card
    html += "<div class='card'><h3>Latest Logged Payload</h3>";
    html += "<div class='payload'>" + lastTransactionPayload + "</div></div>";

    html += "</body></html>";
    server.send(200, "text/html", html);
}

// Handler for Web Payment Form Submission
void handlePay() {
    Serial.println("DEBUG: /pay POST route triggered");
    if (server.hasArg("sender") && server.hasArg("receiver") && server.hasArg("amount")) {
        String sender = server.arg("sender");
        String receiver = server.arg("receiver");
        double amount = server.arg("amount").toDouble();

        send_payload(sender, receiver, amount);
        
        server.sendHeader("Location", "/");
        server.send(303);
    } else {
        server.send(400, "text/plain", "Bad Request: Missing parameters");
    }
}

// GET Fallback: Authorize payment directly via URL query parameters
// Example: http://192.168.4.1/pay-get?sender=08012345678&receiver=09087654321&amount=1500
void handlePayGet() {
    Serial.println("DEBUG: /pay-get GET route triggered");
    if (server.hasArg("sender") && server.hasArg("receiver") && server.hasArg("amount")) {
        String sender = server.arg("sender");
        String receiver = server.arg("receiver");
        double amount = server.arg("amount").toDouble();

        send_payload(sender, receiver, amount);
        
        server.send(200, "text/plain", "Payment Logged! Check your local dashboard.");
    } else {
        server.send(400, "text/plain", "Missing query parameters: sender, receiver, amount");
    }
}

void setup() {
    Serial.begin(115200);

    pinMode(ONBOARD_LED, OUTPUT);
    digitalWrite(ONBOARD_LED, HIGH); // Active LOW: HIGH = OFF

    // Set up ESP32 Access Point
    WiFi.softAP(ssid, password);

    server.on("/", handleRoot);
    server.on("/pay", HTTP_POST, handlePay);
    server.on("/pay-get", HTTP_GET, handlePayGet);
    server.begin();

    delay(1000);
    Serial.println("==============================================");
    Serial.println(" BMONI MOBILE TERMINAL READY                 ");
    Serial.println(" AP: BMONI_OFFLINE_NODE (192.168.4.1)        ");
    Serial.println("==============================================");
}

void loop() {
    server.handleClient();
}