import sys
import os
import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from xvfbwrapper import Xvfb
from selenium.webdriver.firefox.service import Service

def wait_for_page():
    WebDriverWait(browser, 10).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')

# Main Code Start
#configdict = {}
with open(os.path.dirname(__file__) + '/config.json') as json_file: configdict = json.load(json_file)

vdisplay = Xvfb()
vdisplay.start()

service = Service('/usr/bin/geckodriver')

user               = configdict["user"]
password           = configdict["password"]
kudospages         = configdict["kudospages"]
headless           = configdict["headless"]

options = Options()
options.headless = headless
browser = webdriver.Firefox(options=options, service=service)

browser.implicitly_wait(2)

# Navigate to signonpage
print('Signing in to Strava...')
browser.get("https://www.strava.com/login")
wait_for_page()
#username = browser.find_element(By.XPATH, "//input[@id='email']")
#username.send_keys(user + Keys.TAB + password + Keys.ENTER)
browser.find_element(By.XPATH, "//input[@id='email']").send_keys(user + Keys.TAB + password + Keys.ENTER)

for x in range(kudospages):
  wait_for_page()
  KudosButtons = browser.find_elements(By.XPATH, "//button[@title='Give kudos' or @title='Bethe first to give kudos!']")
  print( "Iteration: " + str(x) + ", Kudos buttons found: " + str(len(KudosButtons)) )
  action = ActionChains(browser)

  for KudosButton in KudosButtons:
      browser.execute_script("arguments[0].scrollIntoView();", KudosButton)
      time.sleep(.25)
      action.send_keys(Keys.UP + Keys.UP)
      action.perform()
      time.sleep(1)
      KudosButton.click()
      time.sleep(.25)

  browser.execute_script("window.scrollTo(0, document.body.scrollHeight)")

print("done.... ")
browser.quit()
vdisplay.stop()
sys.exit(0)
