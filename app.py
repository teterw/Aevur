from flask import Flask, render_template_string
from flask import jsonify
import serial
import threading
import time
from collections import deque
import json

app = Flask(__name__)

# Shared data variables (MQ-137 removed)
latest_readings = {"MQ-135": 0, "MQ-138": 0}
alerts = []
baseline = [0, 0]  # Only 2 sensors now
thresholds = [0.2, 0.02]  # MQ-135, MQ-138
alert_status = {"MQ-135": False, "MQ-138": False}

# Store last 20 readings for graph
readings_history = deque(maxlen=20)

# Connect to Arduino
arduino = serial.Serial(port='COM5', baudrate=9600, timeout=1)
time.sleep(2)  # Wait for Arduino reset

def get_baseline(samples=5):
    readings = []
    for _ in range(samples):
        line = arduino.readline().decode('utf-8').strip()
        if line:
            try:
                parts = line.replace(':', '').split()
                # Expecting only MQ-135 and MQ-138 values
                values = list(map(float, parts[1::2]))
                if len(values) == 2:
                    readings.append(values)
            except:
                continue
        time.sleep(1)
    if readings:
        return [sum(x) / len(x) for x in zip(*readings)]
    else:
        return [0, 0]

def sensor_read_loop():
    global latest_readings, alerts, baseline, alert_status, readings_history
    baseline = get_baseline()
    while True:
        line = arduino.readline().decode('utf-8').strip()
        if not line:
            continue
        try:
            parts = line.replace(':', '').split()
            values = list(map(float, parts[1::2]))
            if len(values) != 2:  # Only expecting 2 values now
                continue
            mq135, mq138 = values
            latest_readings = {"MQ-135": mq135, "MQ-138": mq138}
            
            # Add to history with timestamp
            readings_history.append({
                "timestamp": time.time(),
                "MQ-135": mq135,
                "MQ-138": mq138
            })
            
            current_alerts = []
            alert_status = {"MQ-135": False, "MQ-138": False}
            for idx, (name, value, base, thresh) in enumerate(
                zip(["MQ-135", "MQ-138"], values, baseline, thresholds)
            ):
                if value - base > thresh:
                    alert_status[name] = True
                    if name == "MQ-135":
                        gas = "Possible Benzene, Alcohol, or Smoke detected."
                    elif name == "MQ-138":
                        gas = "Possible Acetone or Alcohol detected."
                    current_alerts.append(gas)
            alerts = current_alerts

        except:
            continue
        time.sleep(1)

# Start sensor reading thread
threading.Thread(target=sensor_read_loop, daemon=True).start()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aevur Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            transition: all 0.3s ease;
        }

        /* Dark Theme (Default) */
        body.dark {
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            color: #ffffff;
        }

        /* Light Theme */
        body.light {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            color: #333333;
        }

        .container {
            min-height: 100vh;
            padding: 20px;
            display: grid;
            grid-template-columns: 280px 1fr 320px;
            grid-template-rows: auto 1fr;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        /* Logo Section */
        .logo-section {
            grid-column: 1;
            grid-row: 1;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .logo {
            width: 80px;
            height: 80px;
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }

        .dark .logo {
            background: linear-gradient(135deg, #4a4a4a 0%, #666666 100%);
            border: 2px solid #555;
        }

        .light .logo {
            background: linear-gradient(135deg, #ffffff 0%, #f0f0f0 100%);
            border: 2px solid #ddd;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        .logo::before {
            content: '🔬';
            font-size: 32px;
        }

        .logo-text {
            font-size: 24px;
            font-weight: bold;
        }

        /* Theme Toggle */
        .theme-toggle {
            grid-column: 1;
            grid-row: 2;
            align-self: end;
            margin-bottom: 20px;
        }

        .theme-btn {
            padding: 12px 24px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: all 0.3s ease;
        }

        .dark .theme-btn {
            background: linear-gradient(135deg, #4a4a4a 0%, #666666 100%);
            color: #ffffff;
        }

        .light .theme-btn {
            background: linear-gradient(135deg, #ffffff 0%, #f0f0f0 100%);
            color: #333333;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .theme-btn:hover {
            transform: translateY(-2px);
        }

        /* Sensor Cards */
        .sensor-section {
            grid-column: 2;
            grid-row: 1;
            display: flex;
            gap: 20px;
            align-items: center;
            justify-content: center;
        }

        .sensor-card {
            flex: 1;
            max-width: 200px;
            aspect-ratio: 1;
            border-radius: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 20px;
            transition: all 0.3s ease;
            position: relative;
        }

        .dark .sensor-card {
            background: linear-gradient(135deg, #3a3a3a 0%, #4a4a4a 100%);
            border: 1px solid #555;
        }

        .light .sensor-card {
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border: 1px solid #e0e0e0;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        .sensor-card:hover {
            transform: translateY(-5px);
        }

        .sensor-card.alert {
            border-color: #ff4444;
            box-shadow: 0 0 20px rgba(255, 68, 68, 0.3);
        }

        .sensor-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }

        .sensor-value {
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
            margin-bottom: 5px;
        }

        .sensor-value.alert {
            color: #ff4444;
        }

        .sensor-baseline {
            font-size: 12px;
            opacity: 0.7;
        }

        .sensor-bars {
            display: flex;
            flex-direction: column;
            gap: 8px;
            width: 100%;
        }

        .sensor-bar {
            height: 4px;
            border-radius: 2px;
            width: 100%;
            transition: all 0.3s ease;
        }

        .dark .sensor-bar {
            background: #666;
        }

        .light .sensor-bar {
            background: #ddd;
        }

        /* Control Panel */
        .control-panel {
            grid-column: 3;
            grid-row: 1 / -1;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .control-title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
        }

        .control-btn {
            padding: 15px 20px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: all 0.3s ease;
        }

        .dark .control-btn {
            background: linear-gradient(135deg, #4a4a4a 0%, #5a5a5a 100%);
            color: #ffffff;
        }

        .light .control-btn {
            background: linear-gradient(135deg, #ffffff 0%, #f0f0f0 100%);
            color: #333333;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .control-btn:hover {
            transform: translateY(-2px);
        }

        .ai-assistant {
            margin-top: 30px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .ai-title {
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 15px;
        }

        .ai-chat {
            flex: 1;
            border-radius: 15px;
            min-height: 200px;
            padding: 20px;
            margin-bottom: 15px;
            overflow-y: auto;
        }

        .dark .ai-chat {
            background: linear-gradient(135deg, #2a2a2a 0%, #3a3a3a 100%);
            border: 1px solid #444;
        }

        .light .ai-chat {
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border: 1px solid #ddd;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .ai-input-container {
            display: flex;
            gap: 10px;
        }

        .ai-input {
            flex: 1;
            padding: 12px 20px;
            border: none;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
        }

        .dark .ai-input {
            background: #3a3a3a;
            color: #ffffff;
            border: 1px solid #555;
        }

        .light .ai-input {
            background: #ffffff;
            color: #333333;
            border: 1px solid #ddd;
        }

        .ai-send {
            width: 50px;
            height: 50px;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            transition: all 0.3s ease;
        }

        .dark .ai-send {
            background: linear-gradient(135deg, #4a4a4a 0%, #5a5a5a 100%);
            color: #ffffff;
        }

        .light .ai-send {
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            color: #ffffff;
        }

        /* Graph Section */
        .graph-section {
            grid-column: 2;
            grid-row: 2;
            border-radius: 20px;
            padding: 30px;
            display: flex;
            flex-direction: column;
            min-height: 400px;
        }

        .dark .graph-section {
            background: linear-gradient(135deg, #2a2a2a 0%, #3a3a3a 100%);
            border: 1px solid #444;
        }

        .light .graph-section {
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border: 1px solid #ddd;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        .graph-title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 20px;
            text-align: center;
        }

        .graph-container {
            flex: 1;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            position: relative;
        }

        .dark .graph-container {
            background: #1a1a1a;
            border: 1px solid #333;
        }

        .light .graph-container {
            background: #f8f9fa;
            border: 1px solid #ddd;
        }

        #sensorChart {
            flex: 1;
            min-height: 300px;
            max-height: 350px;
            width: 100%;
        }

        .alert-section {
            margin-top: 20px;
        }

        .alert-item {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            background: rgba(255, 68, 68, 0.1);
            border: 1px solid #ff4444;
            color: #ff4444;
            font-weight: bold;
        }

        /* Responsive Design */
        @media (max-width: 1200px) {
            .container {
                grid-template-columns: 1fr;
                grid-template-rows: auto auto auto auto;
            }
            
            .logo-section {
                grid-column: 1;
                grid-row: 1;
                justify-content: center;
            }
            
            .sensor-section {
                grid-column: 1;
                grid-row: 2;
                flex-wrap: wrap;
            }
            
            .graph-section {
                grid-column: 1;
                grid-row: 3;
            }
            
            .control-panel {
                grid-column: 1;
                grid-row: 4;
            }
            
            .theme-toggle {
                grid-column: 1;
                grid-row: 1;
                align-self: center;
                margin: 0;
                margin-left: auto;
            }
        }

        @media (max-width: 768px) {
            .container {
                padding: 10px;
                gap: 15px;
            }
            
            .sensor-section {
                flex-direction: column;
            }
            
            .sensor-card {
                max-width: 100%;
                width: 100%;
            }
            
            .logo {
                width: 60px;
                height: 60px;
            }
            
            .logo-text {
                font-size: 20px;
            }
        }
    </style>
</head>
<body class="dark">
    <div class="container">
        <div class="logo-section">
            <div class="logo"></div>
            <div class="logo-text">Aevur Dashboard</div>
        </div>

        <div class="theme-toggle">
            <button class="theme-btn" onclick="toggleTheme()">Dark mode</button>
        </div>

        <div class="sensor-section">
            <div class="sensor-card" id="sensor-mq135">
                <div class="sensor-title">MQ-135</div>
                <div class="sensor-value" id="value-mq135">0.000</div>
                <div class="sensor-baseline" id="baseline-mq135">Baseline: 0.000</div>
            </div>
            <div class="sensor-card" id="sensor-mq138">
                <div class="sensor-title">MQ-138</div>
                <div class="sensor-value" id="value-mq138">0.000</div>
                <div class="sensor-baseline" id="baseline-mq138">Baseline: 0.000</div>
            </div>
        </div>

        <div class="graph-section">
            <div class="graph-title">Graph</div>
            <div class="graph-container">
                <canvas id="sensorChart"></canvas>
                <div class="alert-section" id="alerts">
                    <!-- Alerts will be populated here -->
                </div>
            </div>
        </div>

        <div class="control-panel">
            <div class="control-title">Control Panel</div>
            <button class="control-btn" onclick="startMonitoring()">เริ่มการตรวจ</button>
            <button class="control-btn" onclick="stopMonitoring()">หยุดการตรวจ</button>
            <button class="control-btn" onclick="resetBaseline()">รีเซ็ตค่าพื้นฐาน</button>
            <button class="control-btn" onclick="refreshData()">โหลดข้อมูลใหม่</button>
            
            <div class="ai-assistant">
                <div class="ai-title">AI Assistant</div>
                <div class="ai-chat" id="ai-chat">
                    <div style="opacity: 0.6;">AI Assistant ready to help with health analysis...</div>
                </div>
                <div class="ai-input-container">
                    <input type="text" class="ai-input" placeholder="Ask about your health data..." id="ai-input">
                    <button class="ai-send" onclick="sendMessage()">▶</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let monitoringActive = true;
        let sensorChart;

        function initChart() {
            const ctx = document.getElementById('sensorChart').getContext('2d');
            const isDark = document.body.classList.contains('dark');
            
            sensorChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'MQ-135',
                        data: [],
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.1
                    }, {
                        label: 'MQ-138',
                        data: [],
                        borderColor: '#ff6b6b',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: {
                        padding: {
                            top: 20,
                            right: 20,
                            bottom: 20,
                            left: 20
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            grid: {
                                color: isDark ? '#444' : '#ddd'
                            },
                            ticks: {
                                color: isDark ? '#fff' : '#333',
                                maxTicksLimit: 8,
                                callback: function(value) {
                                    return value.toFixed(3);
                                }
                            }
                        },
                        x: {
                            grid: {
                                color: isDark ? '#444' : '#ddd'
                            },
                            ticks: {
                                color: isDark ? '#fff' : '#333',
                                maxTicksLimit: 10
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: {
                                color: isDark ? '#fff' : '#333'
                            }
                        }
                    }
                }
            });
        }

        function updateChart(history) {
            if (!sensorChart || !history || history.length === 0) return;
            
            const labels = history.map((_, index) => `${index + 1}`);
            const mq135Data = history.map(item => item['MQ-135']);
            const mq138Data = history.map(item => item['MQ-138']);
            
            // Calculate dynamic Y-axis range based on data
            const allValues = [...mq135Data, ...mq138Data];
            const minVal = Math.min(...allValues);
            const maxVal = Math.max(...allValues);
            const range = maxVal - minVal;
            const padding = range * 0.1; // 10% padding
            
            // Set Y-axis range with padding
            sensorChart.options.scales.y.min = Math.max(0, minVal - padding);
            sensorChart.options.scales.y.max = maxVal + padding;
            
            sensorChart.data.labels = labels;
            sensorChart.data.datasets[0].data = mq135Data;
            sensorChart.data.datasets[1].data = mq138Data;
            sensorChart.update();
        }

        function toggleTheme() {
            const body = document.body;
            const themeBtn = document.querySelector('.theme-btn');
            
            if (body.classList.contains('dark')) {
                body.classList.remove('dark');
                body.classList.add('light');
                themeBtn.textContent = 'Light mode';
            } else {
                body.classList.remove('light');
                body.classList.add('dark');
                themeBtn.textContent = 'Dark mode';
            }
            
            // Recreate chart with new theme
            if (sensorChart) {
                sensorChart.destroy();
                initChart();
            }
        }

        function sendMessage() {
            const input = document.getElementById('ai-input');
            const chat = document.getElementById('ai-chat');
            
            if (input.value.trim()) {
                const message = document.createElement('div');
                message.style.marginBottom = '10px';
                message.style.padding = '8px 12px';
                message.style.borderRadius = '15px';
                message.style.background = document.body.classList.contains('dark') ? '#4a4a4a' : '#e3f2fd';
                message.textContent = '👤 ' + input.value;
                
                chat.appendChild(message);
                
                // Simple AI response
                setTimeout(() => {
                    const response = document.createElement('div');
                    response.style.marginBottom = '10px';
                    response.style.padding = '8px 12px';
                    response.style.borderRadius = '15px';
                    response.style.background = document.body.classList.contains('dark') ? '#2a4a2a' : '#e8f5e8';
                    response.textContent = '🤖 Based on your sensor data, I recommend monitoring the detected gas levels and ensuring proper ventilation.';
                    
                    chat.appendChild(response);
                    chat.scrollTop = chat.scrollHeight;
                }, 1000);
                
                input.value = '';
                chat.scrollTop = chat.scrollHeight;
            }
        }

        function startMonitoring() {
            monitoringActive = true;
            console.log('Monitoring started');
        }

        function stopMonitoring() {
            monitoringActive = false;
            console.log('Monitoring stopped');
        }

        function resetBaseline() {
            fetch('/reset_baseline', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    console.log('Baseline reset:', data);
                })
                .catch(error => console.error('Error:', error));
        }

        function refreshData() {
            // Reset the graph by clearing history and fetching fresh data
            fetch('/clear_history', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    console.log('History cleared:', data);
                    if (sensorChart) {
                        sensorChart.data.labels = [];
                        sensorChart.data.datasets[0].data = [];
                        sensorChart.data.datasets[1].data = [];
                        sensorChart.update();
                    }
                })
                .catch(error => console.error('Error:', error));
        }

        // Dynamic update for sensor readings and alerts
        async function updateData() {
            if (!monitoringActive) return;
            
            try {
                const response = await fetch('/data');
                const data = await response.json();

                // Update sensor cards
                const sensors = ['MQ-135', 'MQ-138'];
                sensors.forEach((sensor, index) => {
                    const sensorId = sensor.toLowerCase().replace('-', '');
                    const valueElement = document.getElementById(`value-${sensorId}`);
                    const baselineElement = document.getElementById(`baseline-${sensorId}`);
                    const cardElement = document.getElementById(`sensor-${sensorId}`);
                    
                    if (valueElement && baselineElement && cardElement) {
                        const value = data.readings[sensor] || 0;
                        const baseline = data.baseline[index] || 0;
                        const isAlert = data.alert_status[sensor] || false;
                        
                        valueElement.textContent = value.toFixed(3);
                        baselineElement.textContent = `Baseline: ${baseline.toFixed(3)}`;
                        
                        if (isAlert) {
                            cardElement.classList.add('alert');
                            valueElement.classList.add('alert');
                        } else {
                            cardElement.classList.remove('alert');
                            valueElement.classList.remove('alert');
                        }
                    }
                });

                // Update chart with history
                if (data.history && data.history.length > 0) {
                    updateChart(data.history);
                }

                // Update alerts
                const alertsHtml = data.alerts.map(
                    alert => `<div class="alert-item">🚨 ${alert}</div>`
                ).join('');
                document.getElementById('alerts').innerHTML = alertsHtml;

            } catch (e) {
                console.error("Error fetching data:", e);
            }
        }

        // Allow Enter key to send message
        document.getElementById('ai-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // Initialize chart when page loads
        document.addEventListener('DOMContentLoaded', function() {
            initChart();
        });

        // Start periodic updates
        setInterval(updateData, 1000);
        updateData();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(
        HTML_TEMPLATE,
        readings=latest_readings,
        alerts=alerts,
        baseline=baseline,
        alert_status=alert_status
    )

@app.route("/data")
def data():
    return jsonify({
        "readings": latest_readings,
        "alerts": alerts,
        "baseline": baseline,
        "alert_status": alert_status,
        "history": list(readings_history)
    })

@app.route("/reset_baseline", methods=['POST'])
def reset_baseline():
    global baseline
    baseline = get_baseline()
    return jsonify({"status": "success", "baseline": baseline})

@app.route("/clear_history", methods=['POST'])
def clear_history():
    global readings_history
    readings_history.clear()
    return jsonify({"status": "success", "message": "History cleared"})

if __name__ == "__main__":
    app.run(debug=False,host="0.0.0.0", port=5000)