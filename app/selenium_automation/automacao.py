"""
Automação com Selenium para projeto AguaqueAlimenta.
Este script configura e executa um navegador automatizado.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuração do driver
driver = webdriver.Chrome()
driver.maximize_window()

# URL do site
driver.get("https://aplicacoes.mds.gov.br/programacisternas")

# Aguarda o campo usuário estar presente
wait = WebDriverWait(driver, 15)

# Login
usuario = wait.until(EC.presence_of_element_located((By.NAME, "form:usuario")))
senha = wait.until(EC.presence_of_element_located((By.NAME, "form:senha")))

usuario.send_keys("fabiano.lima")
senha.send_keys("123")

# Botão Acessar
btn_acessar = wait.until(EC.element_to_be_clickable(
    (By.XPATH, "//input[@type='submit' and @value='Acessar']")))
btn_acessar.click()

print("Login realizado com sucesso!")

# Clicar no botão 'Menu'
menu_button = wait.until(EC.element_to_be_clickable(
    (By.XPATH, "//a[@class='button' and contains(., 'Menu')]")))
menu_button.click()

print("Botão Menu clicado.")

# Passar o mouse por cima de 'Primeira Água'
primeira_agua = wait.until(EC.presence_of_element_located(
    (By.XPATH, "//a[contains(text(), 'Primeira Água')]")
))

familia_link = wait.until(EC.presence_of_element_located(
    (By.XPATH, "//a[contains(text(), 'Família')]")
))

actions = ActionChains(driver)

# Encadeia: passa o mouse sobre Primeira Água e clica em Família SEM
# soltar o mouse
actions.move_to_element(primeira_agua).move_to_element(
    familia_link).click().perform()

print("Clicou em 'Família' com sucesso.")

# Fim do teste
# driver.quit()
