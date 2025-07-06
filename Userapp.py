from flask import Flask, render_template_string
from flask import jsonify
import serial
import threading
import time
import requests

app = Flask(__name__)

# Shared data variables (removed MQ-137)
latest_readings = {"MQ-135": 0, "MQ-138": 0}
alerts = []
baseline = [0, 0]  # Only 2 sensors now
thresholds = [0.2, 0.02]  # Thresholds for MQ-135 and MQ-138
alert_status = {"MQ-135": False, "MQ-138": False}

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
                values = list(map(float, parts[1::2]))
                if len(values) == 2:  # Only expecting 2 values now
                    readings.append(values)
            except:
                continue
        time.sleep(1)
    if readings:
        return [sum(x) / len(x) for x in zip(*readings)]
    else:
        return [0, 0]

def sensor_read_loop():
    global latest_readings, alerts, baseline, alert_status
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
            alerts = current_alerts

        except:
            continue
        time.sleep(1)

# Start sensor reading thread
threading.Thread(target=sensor_read_loop, daemon=True).start()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ASMA-Aevur</title>
    <link rel="stylesheet" href="style.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Prompt:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap');
        * { box-sizing: border-box; padding: 0; margin: 0; font-family: "Prompt", sans-serif; }
        body { padding: 0 80px; }
        button { padding: 8px 24px; border: none; border-radius: 8px; cursor: pointer; transition: transform 0.3s ease; }
        button:hover { transform: scale(1.1); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
        .menu-toggle { display: none; flex-direction: column; cursor: pointer; gap: 4px; }
        .menu-toggle span { width: 25px; height: 3px; background-color: #446C85; transition: 0.3s; }
        nav { display: flex; justify-content: space-between; align-items: center; background-color: white; width: 100%; margin-top: 60px; padding: 20px 40px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); border-radius: 24px; position: relative; }
        nav img { width: 128px; height: 44px; }
        nav ul { display: flex; align-items: center; gap: 32px; list-style: none; }
        nav ul li { transition: transform 0.3s ease; }
        nav ul li:hover { transform: scale(1.1); }
        nav ul a { text-decoration: none; color: black; font-size: 24px; transition: transform 0.3s ease; }
        nav ul a:hover { color: #446C85; }
        .login-btn { background-color: #458F8E; color: white; font-size: 24px; }
        .hero-container { margin-top: 60px; display: flex; justify-content: center; position: relative; }
        .hero-info-con { width: 1062px; height: 380px; display: flex; flex-direction: column; justify-content: center; align-items: center; background-color: white; gap: 32px; border: 3px solid #59AEAD; border-radius: 32px; padding: 24px; }
        .hero-info-con img { width: 358px; height: 124px; }
        .hero-info-con h1 { font-size: 32px; font-weight: 500; }
        .hero-info-con p { text-align: center; font-size: 20px; color: #808080; }
        .sq-blue { position: absolute; width: 100%; height: 320px; background-color: #446C85; border-radius: 24px; z-index: -1; top: 32px; }
        .sq-white1, .sq-white2 { width: 864px; height: 10px; background-color: white; }
        .sq-white1 { position: absolute; top: -3px; }
        .sq-white2 { position: absolute; bottom: -3px; }
        .service-container { margin-top: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        .service-title-con { display: flex; flex-direction: column; align-items: center; }
        .service-title-con h1 { font-size: 32px; font-weight: 400; }
        .service-title-con p { font-size: 20px; color: #808080; }
        .card-con { margin-top: 32px; display: flex; gap: 16px; flex-wrap: wrap; justify-content: center; }
        .service-card { display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 16px; padding: 24px; border-radius: 8px; flex: 1; min-width: 250px; }
        .service-card img { object-position: top right; width: 100%; height: 200px; border-radius: 8px; }
        .service-card h2 { color: white; font-weight: 400; font-size: 24px; }
        .service-card p { color: lightgray; }
        .card1, .card2 { background-color: #446C85; }
        .result-container { margin-top: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        .result-title-con { display: flex; flex-direction: column; align-items: center; }
        .result-title-con h1 { font-size: 32px; font-weight: 400; }
        .result-title-con p { font-size: 20px; color: #808080; }
        .result-con { margin-top: 32px; display: flex; width: 100%; gap: 24px; flex-wrap: wrap; }
        .result-card { display: flex; justify-content: center; align-items: center; gap: 24px; border: 1px solid black; padding: 20px 30px; width: 100%; border: 2px solid lightgray; border-radius: 8px; flex: 1; min-width: 300px; }
        .result-card img { object-fit: cover; height: 100%; }
        .result-detail { display: flex; flex-direction: column; gap: 16px; }
        .result-detail h2 { font-size: 24px; font-weight: 500; }
        .result-tag { font-size: 20px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .tag { background-color: lightgray; padding: 2px 12px; border-radius: 24px; color: white; }
        .tag.tag-success { background-color: #03C03C; }
        .tag.tag-danger { background-color: #ED1B24; }
        .result-detail p { font-size: 20px; }
        .result-card.success { background-color: #CDF2D8; border: 2px solid #028028; }
        .result-card.danger { background-color: #FBD1D3; border: 2px solid #B2141B; }
        .sugges-container { margin-top: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 32px; }
        .sugges-title-con { display: flex; flex-direction: column; align-items: center; }
        .sugges-title-con h1 { font-size: 32px; font-weight: 400; }
        .sugges-title-con p { font-size: 20px; color: #808080; }
        .sugges-con { display: flex; gap: 24px; flex-wrap: wrap; justify-content: center; }
        .sugges-card { display: flex; flex-direction: column; padding: 24px; gap: 16px; border: 2px solid #335163; border-radius: 8px; flex: 1; min-width: 280px; }
        .title-con { display: flex; gap: 8px; font-size: 24px; color: #446C85; flex-wrap: wrap; align-items: center; }
        .title-con .tag { background-color: #446C85; color: white; padding: 2px 16px; border-radius: 24px; }
        .sugges-des { font-size: 20px; font-weight: 200; }
        .meet-container { margin-top: 60px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 32px; }
        .meet-title-con>h1 { font-size: 32px; font-weight: 400; text-align: center; }
        .meet-btn-con { display: flex; gap: 24px; flex-wrap: wrap; justify-content: center; }
        .meet-btn { font-size: 24px; }
        .meet-btn.success { background-color: #458F8E; color: white; }
        .ai-container { margin: 60px 0px; width: 100%; display: flex; flex-direction: column; gap: 24px; }
        .ai-container h1 { font-weight: 400; font-size: 32px; }
        .ai-container textarea { width: 100%; height: 200px; padding: 8px 20px; border-radius: 8px; border: 2px solid #458F8E; font-size: 20px; resize: vertical; }
        .ai-container textarea::placeholder { color: #808080; font-size: 20px; }
        .ai-input { display: flex; justify-content: space-between; gap: 24px; }
        .ai-input input { width: 100%; padding: 20px; border-radius: 8px; border: 2px solid #458F8E; }
        .ai-input input::placeholder { color: #808080; font-size: 20px; }
        .ai-input input:focus { font-size: 20px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
        .ai-input button { background-color: #458F8E; color: white; font-size: 24px; white-space: nowrap; }
        .alert { color: red; font-weight: bold; }
        @media (max-width: 768px) {
            body { padding: 0 20px; }
            nav { margin-top: 20px; padding: 15px 20px; flex-wrap: wrap; }
            nav img { width: 100px; height: 35px; }
            .menu-toggle { display: flex; }
            nav ul { display: none; width: 100%; flex-direction: column; gap: 16px; margin-top: 20px; }
            nav ul.active { display: flex; }
            nav ul a { font-size: 20px; }
            .login-btn { font-size: 18px; padding: 6px 16px; }
            .hero-container { margin-top: 30px; }
            .hero-info-con { width: 100%; height: auto; padding: 20px; gap: 20px; }
            .hero-info-con img { width: 250px; height: 86px; }
            .hero-info-con h1 { font-size: 24px; text-align: center; }
            .hero-info-con p { font-size: 16px; }
            .sq-blue { height: auto; min-height: 200px; }
            .sq-white1, .sq-white2 { width: 100%; }
            .service-container { margin-top: 40px; }
            .service-title-con h1 { font-size: 28px; text-align: center; }
            .service-title-con p { font-size: 18px; }
            .card-con { flex-direction: column; gap: 20px; }
            .service-card { min-width: 100%; }
            .service-card h2 { font-size: 20px; }
            .result-container { margin-top: 40px; }
            .result-title-con h1 { font-size: 28px; text-align: center; }
            .result-con { flex-direction: column; gap: 16px; }
            .result-card { flex-direction: column; text-align: center; min-width: 100%; gap: 16px; }
            .result-card img { width: 80px; height: 80px; }
            .result-tag { justify-content: center; }
            .sugges-container { margin-top: 40px; }
            .sugges-title-con h1 { font-size: 28px; text-align: center; }
            .sugges-con { flex-direction: column; gap: 16px; }
            .sugges-card { min-width: 100%; }
            .title-con { font-size: 20px; justify-content: center; text-align: center; }
            .meet-container { margin-top: 40px; }
            .meet-title-con>h1 { font-size: 24px; }
            .meet-btn-con { flex-direction: column; align-items: center; gap: 16px; }
            .meet-btn { font-size: 20px; width: 200px; }
            .ai-container { margin: 40px 0px; }
            .ai-container h1 { font-size: 24px; }
            .ai-container textarea { height: 150px; font-size: 16px; }
            .ai-input { flex-direction: column; gap: 16px; }
            .ai-input input { padding: 15px; font-size: 16px; }
            .ai-input input::placeholder { font-size: 16px; }
            .ai-input button { font-size: 20px; }
        }
        @media (max-width: 1024px) and (min-width: 769px) {
            body { padding: 0 40px; }
            .hero-info-con { width: 90%; }
            .card-con { justify-content: center; }
            .service-card { flex: 1 1 calc(50% - 16px); max-width: calc(50% - 16px); }
            .result-con { flex-direction: column; }
            .sugges-con { flex-direction: column; }
        }
        @media (max-width: 480px) {
            body { padding: 0 15px; }
            nav { padding: 10px 15px; }
            .hero-info-con { padding: 15px; gap: 15px; }
            .hero-info-con img { width: 200px; height: 69px; }
            .hero-info-con h1 { font-size: 20px; }
            .hero-info-con p { font-size: 14px; }
            .service-title-con h1, .result-title-con h1, .sugges-title-con h1 { font-size: 24px; }
            .meet-title-con>h1 { font-size: 20px; }
            .ai-container h1 { font-size: 20px; }
        }
    </style>
</head>

<body>

    <section class="hero-container">
        <div class="hero-info-con">
            <img src="https://i.postimg.cc/vBdW4fTx/Pitch-for-change-Aevur.png">
            <h1>เช็กสุขภาพล่วงหน้า เพื่อชีวิตที่ยืนยาว</h1>
            <p>Aevur วิเคราะห์ความเสี่ยงของโรคจากข้อมูลสุขภาพของคุณ <br>เพื่อช่วยป้องกันก่อนสายเกินไป — เพราะสุขภาพดี
                เริ่มจากความเข้าใจตัวเอง</p>
        </div>
        <div class="sq-blue"></div>
        <div class="sq-white1"></div>
        <div class="sq-white2"></div>
    </section>
    
    <section class="result-container">
        <div class="result-title-con">
            <h1>ผลการวิเคราะห์สำหรับคุณ</h1>
            <p>Health insights</p>
        </div>
        <div class="result-con" id="result-cards">
            <!-- Cards will be filled by JS -->
        </div>
        <div id="alerts"></div>
    </section>

    <section class="sugges-container">
        <div class="sugges-title-con">
            <h1>คำแนะนำสำหรับคุณ</h1>
            <p>Health insights for You</p>
        </div>
        <div class="sugges-con">
            <div class="sugges-card">
                <div class="title-con">
                    <p>คำแนะนำเพื่อสุขภาพ : </p>
                    <div class="tag">...</div>
                </div>
                <div>
                    <p>Lorem ipsum dolor sit amet consectetur. Eros arcu sit dictum fusce ac aliquam. Orci vel duis sed.
                    </p>
                </div>
            </div>
            <div class="sugges-card">
                <div class="title-con">
                    <p>คำแนะนำเพื่อสุขภาพ : </p>
                    <div class="tag">...</div>
                </div>
                <div>
                    <p>Lorem ipsum dolor sit amet consectetur. Eros arcu sit dictum fusce ac aliquam. Orci vel duis sed.
                    </p>
                </div>
            </div>
            <div class="sugges-card">
                <div class="title-con">
                    <p>คำแนะนำเพื่อสุขภาพ : </p>
                    <div class="tag">...</div>
                </div>
                <div class="sugges-desc">
                    <p>Lorem ipsum dolor sit amet consectetur. Eros arcu sit dictum fusce ac aliquam. Orci vel duis sed.
                    </p>
                </div>
            </div>
        </div>
    </section>

    <section class="ai-container">
        <h1>Aevur.AI ช่วยตอบคำถามที่คุณสงสัย ?</h1>
        <textarea readonly placeholder="output here..."></textarea>
        <div class="ai-input">
            <input type="text" placeholder="พิมพ์ข้อความ">
            <button>ส่ง</button>
        </div>
    </section>

    <script>
        function toggleMenu() {
            const menu = document.getElementById('nav-menu');
            menu.classList.toggle('active');
        }
        document.querySelectorAll('nav ul a').forEach(link => {
            link.addEventListener('click', () => {
                document.getElementById('nav-menu').classList.remove('active');
            });
        });
        document.addEventListener('click', (e) => {
            const nav = document.querySelector('nav');
            const menu = document.getElementById('nav-menu');
            const toggle = document.querySelector('.menu-toggle');
            if (!nav.contains(e.target) && menu.classList.contains('active')) {
                menu.classList.remove('active');
            }
        });

        // Dynamic update for sensor readings and alerts (removed MQ-137)
        async function updateData() {
            try {
                const response = await fetch('/data');

                const data = await response.json();

                // Fill result cards (removed MQ-137)
                const cards = [
                    {
                        id: "mq138",
                        disease: "Mq-138",
                        img: "https://bz49dmux6d.ufs.sh/f/1Q7cAF0oN6JTLqYK7j5kX0SfouG3gHjNi7P1CsqceVOvn68A",
                        sensor: "MQ-138",
                    },
                    {
                        id: "mq135",
                        disease: "Mq-135",
                        img: "https://bz49dmux6d.ufs.sh/f/1Q7cAF0oN6JTml6DJ2HxG6E3TILBoXrtsVONDbQPY0Kinl1F",
                        sensor: "MQ-135",
                    }
                ];
                let html = "";
                for (const card of cards) {
                    const danger = data.alert_status[card.sensor];
                    html += `
                    <div class="result-card ${danger ? "danger" : "success"}" id="card-${card.id}">
                        <div>
                            <img src="${card.img}">
                        </div>
                        <div class="result-detail">
                            <h2>${card.disease}</h2>
                            <div class="result-tag">
                                <p>ผลตรวจ :</p>
                                <div class="tag ${danger ? "tag-danger" : "tag-success"}" id="tag-${card.id}">
                                    ${danger ? "มีความเสี่ยง" : "ไม่มีความเสี่ยง"}
                                </div>
                            </div>
                            <p>ค่า : ${data.readings[card.sensor].toFixed(3)} (baseline: ${parseFloat(data.baseline[card.baselineIdx]).toFixed(3)})</p>
                        </div>
                    </div>
                    `;
                }
                document.getElementById('result-cards').innerHTML = html;

                // Alerts
                document.getElementById('alerts').innerHTML = data.alerts.map(
                    alert => `<div class="alert">${alert}</div>`
                ).join('');
            } catch (e) {
                console.error("Error fetching data:", e);
            }
        }

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
        "alert_status": alert_status
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



    