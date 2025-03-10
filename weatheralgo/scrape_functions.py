import logging
import pandas as pd
from selenium.webdriver.common.by import By
from datetime import datetime, timedelta
from dateutil import tz
import pytz
import requests
import xml.etree.ElementTree as ET

from weatheralgo.clients import client
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

    
def scrape_temperature(driver, url) -> list[str, float]:
    
    try:
        driver.get(url)
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'path[fill="#2caffe"]'))
        )
        path_elements = driver.find_elements(By.CSS_SELECTOR, 'path[fill="#2caffe"]')

        datetemp_list = [path.get_attribute("aria-label") for path in path_elements]
       
        date = [', '.join(i.split(', ')[0:3]) for i in datetemp_list]
        temp = [float(i.split(', ')[-1].split(' ')[0][:-1]) for i in datetemp_list]
    
        return [date, temp]  # Return date and temperature
        
    except Exception as e:
        logging.error(f"Error scrape_temperature: {e}")
        return None


def xml_scrape(xml_url, timezone):

    try:
        response = requests.get(xml_url)
        root = ET.fromstring(response.content)

        start_times = root.findall('.//start-valid-time')
        dates = [time.text for time in start_times]

        temperature_element = root.find('.//temperature[@type="hourly"]')
        value_elements = temperature_element.findall('.//value')
        temp = [int(value.text) for value in value_elements if isinstance(value.text, str)]
        temp_length = len(temp)
 
        forecasted = pd.DataFrame({'DateTime': dates[:temp_length], 'Temperature': temp})
        forecasted['DateTime'] = pd.to_datetime(forecasted['DateTime'])
        forecasted = forecasted.sort_values(by='DateTime')

        denver_today = datetime.now(timezone).day

        next_day_high = forecasted[forecasted['DateTime'].dt.day == denver_today]['Temperature'][::-1].idxmax()
        date = forecasted['DateTime'].iloc[next_day_high]
        hour_of_high = forecasted['DateTime'].iloc[next_day_high].hour
        temp_high = forecasted['Temperature'].iloc[next_day_high]

        return [date, hour_of_high, temp_high]

    except Exception as e:
      print(e)


def iso_to_local_time(iso_string, timezone):
    
    utc_time = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    local_tz = tz.gettz(timezone)
    local_time = utc_time.astimezone(local_tz).date()
    
    return local_time.isoformat()

def trade_today(market, timezone):

    try:
        today = datetime.now(timezone)
        todays_date = today.strftime('%y%b%d').upper()
        event = f'{market}-{todays_date}'
        orders = client.get_orders(event_ticker=event)['orders']
    
        if len(orders) >= 1:
            order_list = [iso_to_local_time(iso_string = i['created_time'], timezone=str(timezone)) for i in orders]
            if str(today.date()) in order_list:
             
                return True
            else:
                return False
        else:
            return False

    except Exception as e:
        logging.error(f"Error Trade Today: {e}")

def begin_scrape(scraping_hours, expected_high_date, timezone):
    
    try:
        today = datetime.now(timezone)

        start_scrape = today >= expected_high_date - timedelta(minutes=scraping_hours[0])
        end_scrape = today <= expected_high_date + timedelta(minutes=scraping_hours[1])

        if start_scrape and end_scrape:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"Error in begin_scrape: {e}")

def permission_to_scrape(market, timezone, scraping_hours, expected_high_date, market_dict):
    
    # timezone_lower = datetime.now(timezone)
    # timezone_lower_bound = timezone_lower.hour >= 9
    
    # timezone_upper = datetime.now(timezone)
    # timezone_upper_bound = timezone_upper.hour <= 21
    
    trade_today_check = trade_today(market, timezone)
    begin_scrape_check = begin_scrape(scraping_hours, expected_high_date, timezone)
    market_dict_check = market_dict[market]['trade_executed'] == None
    
    if all([not trade_today_check, begin_scrape_check, market_dict_check]): #timezone_lower_bound, timezone_upper_bound,
    
        return True
    else:
        return False
    
        

    