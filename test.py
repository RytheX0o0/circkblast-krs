from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
import time
import threading

# Initialize Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# URL to scrape
url = "https://crex.live/scoreboard/RKP/1OH/98th-Match/IS/MN/ita-vs-swe-98th-match-european-t10-championship-2024/live"

# Global variable to store the scraped data
scraped_data = {
    "series_name": "",
    "live_score_card": "",
    "live_data": "",
    "batsmen_career": [],
    "player_strike": [],
    "on_strike_batsman": ""  # To track which batsman is on strike
}

# Function to scrape data using Selenium
def scrape_data():
    global scraped_data
    # Set up Firefox options and GeckoDriver for headless mode
    options = Options()
    options.binary_location = '/Applications/Firefox.app/Contents/MacOS/firefox'
    options.headless = True  # Run in headless mode (no browser window)
    service = Service('/usr/local/bin/geckodriver')

    # Initialize WebDriver for Firefox in headless mode
    driver = webdriver.Firefox(service=service, options=options)

    while True:
        # Open the page
        driver.get(url)
        time.sleep(2)  # Wait for the page to load completely

        # Get the page source and parse it with BeautifulSoup
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Scrape data from the specified classes
        series_name = soup.find('div', class_='series-name mob-none')
        live_score_card = soup.find('div', class_='live-score-card')
        live_data = soup.find('div', class_='live-data odds-session-left odd-session-common width100')

        # Scrape the batsmen and bowler career data
        batsmen_career = soup.find_all('div', class_='batsmen-career-wrapper')
        batsmen_career_data = [career.text.strip() for career in batsmen_career if career]

        # Scrape the player strike rate data
        player_strike = soup.find_all('div', class_='player-strike-wrapper')
        player_strike_data = [strike.text.strip() for strike in player_strike if strike]

        # Find the batsman on strike using the class "circle-strike-icon" or "circle-strike"
        batsman_on_strike = soup.find('div', class_='circle-strike-icon icon-left') or soup.find('div', class_='circle-strike')

        # Prepare the on-strike batsman name
        batsman_on_strike_name = "N/A"
        if batsman_on_strike:
            previous_batsman = batsman_on_strike.find_previous('div', class_='batsmen-career-wrapper')
            if previous_batsman:
                batsman_on_strike_name = previous_batsman.text.strip()

        # Prepare the new data, handling None cases with fallback "N/A"
        new_data = {
            "series_name": series_name.text.strip() if series_name else "N/A",
            "live_score_card": live_score_card.text.strip() if live_score_card else "N/A",
            "live_data": live_data.text.strip() if live_data else "N/A",
            "batsmen_career": batsmen_career_data,
            "player_strike": player_strike_data,
            "batsman_on_strike": batsman_on_strike_name
        }

        # Only emit the data if there is a change
        if new_data != scraped_data:
            scraped_data.update(new_data)
            socketio.emit('update_data', scraped_data)

        time.sleep(1)  # Wait a second before scraping again for near real-time updates

# Start the scraper in a separate thread to continuously scrape data
scraper_thread = threading.Thread(target=scrape_data)
scraper_thread.daemon = True
scraper_thread.start()

# Route to display the scraped data
@app.route('/')
def index():
    html_template = '''
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Cricket Data</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Roboto', sans-serif;
            background-color: #0d1b2a;
            color: #fff;
            margin: 0;
            padding: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
        }
        .container {
            max-width: 960px;
            background-color: #1b263b;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        h2 {
            text-align: center;
            color: #e76f51;
            margin-bottom: 20px;
        }
        .section-title {
            font-size: 18px;
            color: #f4a261;
            margin: 10px 0;
        }
        .data-box {
            background-color: #415a77;
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        .data-box:hover {
            background-color: #e76f51;
            transform: translateY(-5px);
        }
        .strike-on {
            color: #2a9d8f;
            font-weight: bold;
        }
        @media (max-width: 768px) {
            .container {
                width: 100%;
                padding: 15px;
            }
            h2 {
                font-size: 22px;
            }
            .section-title {
                font-size: 16px;
            }
            .data-box {
                padding: 8px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Live Cricket Data</h2>
        <div class="section">
            <div class="section-title">Series Name</div>
            <div id="series_name" class="data-box">{{ series_name }}</div>
        </div>
        <div class="section">
            <div class="section-title">Live Score Card</div>
            <div id="live_score_card" class="data-box">{{ live_score_card }}</div>
        </div>
        <div class="section">
            <div class="section-title">Live Data</div>
            <div id="live_data" class="data-box">{{ live_data }}</div>
        </div>
        <div class="section">
            <div class="section-title">Batsmen Career Data</div>
            <div id="batsmen_career"></div>
        </div>
        <div class="section">
            <div class="section-title">Player Strike Rates</div>
            <div id="player_strike"></div>
        </div>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.1.3/socket.io.min.js"></script>
    <script type="text/javascript">
        var socket = io();
        socket.on('update_data', function(data) {
            document.getElementById('series_name').innerHTML = data.series_name;
            document.getElementById('live_score_card').innerHTML = data.live_score_card;
            document.getElementById('live_data').innerHTML = data.live_data;
            var batsmenCareerHtml = '';
            data.batsmen_career.forEach(function(career) {
                if (career.includes(data.batsman_on_strike)) {
                    batsmenCareerHtml += '<div class="data-box">' + career + '<span class="strike-on">On Strike</span></div>';
                } else {
                    batsmenCareerHtml += '<div class="data-box">' + career + '</div>';
                }
            });
            document.getElementById('batsmen_career').innerHTML = batsmenCareerHtml;
            var playerStrikeHtml = '';
            data.player_strike.forEach(function(strike) {
                playerStrikeHtml += '<div class="data-box">' + strike + '</div>';
            });
            document.getElementById('player_strike').innerHTML = playerStrikeHtml;
        });
    </script>
</body>
</html>
'''
    return render_template_string(html_template,
                                  series_name=scraped_data["series_name"],
                                  live_score_card=scraped_data["live_score_card"],
                                  live_data=scraped_data["live_data"])

if __name__ == "__main__":
    socketio.run(app, debug=True)
