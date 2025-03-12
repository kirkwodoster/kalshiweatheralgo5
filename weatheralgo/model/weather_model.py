from fake_useragent import UserAgent
import logging
import tempfile
import time
import random
import subprocess
import uuid
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from weatheralgo import trade_functions
from weatheralgo import scrape_functions
from weatheralgo import util_functions
from weatheralgo import inputs



def kill_chrome_processes():
    try:
        # Find and kill any existing Chrome processes
        subprocess.run(['pkill', '-f', 'chrome'], check=False)
        # Give it a moment to clean up
        time.sleep(2)
    except Exception as e:
        logging.error(f"Error killing Chrome processes: {e}")

# Initialize Selenium WebDriver
def initialize_driver():
    
    unique_user_data_dir = os.path.join(tempfile.gettempdir(), f"chrome-{uuid.uuid4()}")
    kill_chrome_processes()

    # chrome_options = Options()
    # chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument(f"--user-data-dir={unique_user_data_dir}")
    # chrome_options.add_argument("--single-process")
    # chrome_options.add_argument("--disable-dev-shm-usage")
    # chrome_options.add_argument("--remote-debugging-port=9222")
    # # chrome_options.add_argument("--user-data-dir=/tmp/chrome-data")
    # chrome_options.add_argument("--headless")
    # chrome_options.add_argument('--log-level=3')
    # ua = UserAgent()
    # chrome_options.add_argument(f"user-agent={ua.random}")
    
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--user-data-dir=/tmp/chrome-data")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--log-level=3')
    ua = UserAgent()
    chrome_options.add_argument(f"user-agent={ua.random}")
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)


# Main function to scrape and process data
def scrape_dynamic_table(driver, lr_length, count, scraping_hours, yes_price, locations):
    
    util_functions.logging_settings()
    temperatures = []
    
    restart_threshold = 40  # Restart WebDriver every 15 iterations
    loop_counter = 0
    
    rand = random.randint(2, 4)

    market_dict = inputs.market_dict
    util_functions.market_dict_update(market_dict)
    
    while True:

        model_inputs = inputs.model_input
        market_dict = util_functions.retrieve_market_dict()
        print(market_dict)
        
        for i in locations:
            market, timezone, url, xml_url = model_inputs(i)
        
            forecasted_high = inputs.forecasted_high_gate(
                                                         market_dict=market_dict,
                                                         market=market,
                                                         xml_url=xml_url,
                                                         timezone=timezone
                                                        )
            
            if forecasted_high:
                current_timezone, forecasted_high_date = forecasted_high
                current_timezone = current_timezone.date()                
                market_dict[market]['current_timezone'] = current_timezone
                market_dict[market]['forecasted_high'] = forecasted_high_date
                market_dict[market]['trade_executed'] = None
                print(forecasted_high_date)
                
            forecasted_high_date = market_dict[market]['forecasted_high']       

            permission_scrape = scrape_functions.permission_to_scrape(
                                                                    market=market, 
                                                                    timezone=timezone, 
                                                                    scraping_hours=scraping_hours, 
                                                                    expected_high_date=forecasted_high_date,
                                                                    market_dict=market_dict
                                                                    )
                       
            print(f'forecasted_high_date {forecasted_high_date}')

            time.sleep(rand)
            try:
                print(f'Permission Scrape: {permission_scrape} market: {market}')
                if permission_scrape:
                    scrape = scrape_functions.scrape_temperature(driver=driver, url=url)
                    current_temp = scrape[1][-1]
                    temperatures = scrape[1]
                    
                    print(f'Market: {market}')
                    print(f'Current Temp: {current_temp}')
                    print(f'Temperature: {temperatures}')
                    print(f'expected high date {forecasted_high_date}')
                    print(market_dict[market]['trade_executed'])
                    
                    trade_execution = trade_functions.max_or_trade_criteria_met(
                                                                                current_temp=current_temp,
                                                                                market = market, 
                                                                                yes_price=yes_price,
                                                                                count=count,
                                                                                temperatures=temperatures,
                                                                                timezone=timezone,
                                                                                lr_length=lr_length,
                                                                              )
                    
                    if trade_execution:
                        market_dict[market]['trade_executed'] = trade_execution
                        
                util_functions.market_dict_update(market_dict=market_dict)
 

                time.sleep(rand)    
                    
                is_order_filled = util_functions.order_filled(market=market, timezone=timezone)
                    
                if is_order_filled:
                    logging.info(f'Order filled and saved: {market}')
                else:
                    continue
        
            except Exception as e:
                logging.error(f"in main loop: {e}")

        loop_counter += 1
        if loop_counter >= restart_threshold:
            logging.info("Restarting WebDriver to prevent stale sessions...")
            driver.quit()
            driver = initialize_driver()
            loop_counter = 0  # Reset counter

        
        time.sleep(rand)
