"""Real-browser smoke coverage for the primary NiceGUI workflow."""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest

selenium = pytest.importorskip("selenium")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("RUN_BROWSER_TESTS") != "1",
        reason="set RUN_BROWSER_TESTS=1 to run the real-browser smoke test",
    ),
]

PROJECT_ROOT = Path(__file__).parents[1]


def find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def create_browser() -> webdriver.Remote:
    chrome = (
        shutil.which("google-chrome")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )
    if chrome:
        options = webdriver.ChromeOptions()
        options.binary_location = chrome
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1600,1000")
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        return webdriver.Chrome(options=options)

    firefox = shutil.which("firefox")
    if firefox:
        options = webdriver.FirefoxOptions()
        options.binary_location = firefox
        options.add_argument("-headless")
        return webdriver.Firefox(options=options)

    pytest.skip("Chrome/Chromium or Firefox is required for browser smoke tests")


def wait_for_server(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(
                f"GUI server exited early\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("GUI server did not become ready within 20 seconds")


def click_text(driver: webdriver.Remote, text: str) -> None:
    xpath = f'//*[normalize-space(text())="{text}"]'
    element = WebDriverWait(driver, 10).until(
        lambda browser: next(
            (
                candidate
                for candidate in browser.find_elements(By.XPATH, xpath)
                if candidate.is_displayed() and candidate.is_enabled()
            ),
            False,
        )
    )
    element.click()


def test_primary_gui_workflow_in_real_browser() -> None:
    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)
    env["RV32I_GUI_HOST"] = "127.0.0.1"
    env["RV32I_GUI_PORT"] = str(port)
    # Selenium owns browser startup; suppress NiceGUI's desktop auto-open.
    env["BROWSER"] = "true"
    process = subprocess.Popen(
        [sys.executable, "gui/app.py"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    driver = None
    try:
        wait_for_server(url, process)
        driver = create_browser()
        driver.set_window_size(1440, 1000)
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        status = lambda browser: browser.find_element(By.ID, "sim-status").text

        wait.until(lambda browser: "Compiled OK" in status(browser))

        driver.find_element(By.ID, "sim-example").click()
        click_text(driver, "I/O / Hello terminal")
        wait.until(lambda browser: "Compiled OK" in status(browser))
        wait.until(
            lambda browser: "Hello from RISC-V!"
            in browser.find_element(By.TAG_NAME, "body").text
        )
        driver.find_element(By.ID, "sim-run").click()
        wait.until(lambda browser: status(browser) == "Halted")
        driver.find_element(By.ID, "sim-terminal").click()
        wait.until(
            lambda browser: "Hello from RISC-V!"
            in browser.find_element(By.CSS_SELECTOR, ".xterm-rows").text
        )
        click_text(driver, "\u2715")

        driver.find_element(By.ID, "sim-compile").click()
        wait.until(lambda browser: "Compiled OK" in status(browser))

        driver.find_element(By.ID, "sim-step").click()
        wait.until(
            lambda browser: "CYCLE:0000" not in browser.find_element(
                By.TAG_NAME, "body"
            ).text
        )
        driver.find_element(By.ID, "sim-reset").click()
        wait.until(lambda browser: status(browser) == "Reset")

        click_text(driver, "Multi-Cycle")
        wait.until(lambda browser: "Multi-Cycle mode" in status(browser))
        assert not driver.find_elements(By.ID, "sim-step-clock")
        driver.find_element(By.ID, "sim-step").click()
        wait.until(lambda browser: "one clock advanced" in status(browser))

        driver.find_element(By.ID, "sim-reset").click()
        click_text(driver, "Pipeline")
        wait.until(lambda browser: "Pipeline mode" in status(browser))
        splitter = wait.until(
            lambda browser: browser.find_element(
                By.CSS_SELECTOR, ".pipeline-splitter"
            )
        )
        register_pane = splitter.find_element(
            By.CSS_SELECTOR, ".pipeline-register-pane"
        )
        visualization_pane = splitter.find_element(
            By.CSS_SELECTOR, ".pipeline-visualization-pane"
        )
        assert visualization_pane.rect["width"] > register_pane.rect["width"] * 2
        assert abs(visualization_pane.rect["y"] - register_pane.rect["y"]) <= 1
        driver.find_element(By.ID, "sim-step").click()
        wait.until(lambda browser: "one clock advanced" in status(browser))

        driver.find_element(By.ID, "sim-reset").click()
        click_text(driver, "Single-Cycle")
        wait.until(lambda browser: "Single-Cycle mode" in status(browser))
        first_instruction = wait.until(
            lambda browser: browser.find_element(
                By.CSS_SELECTOR, ".asm-line[data-addr]"
            )
        )
        first_instruction.click()
        time.sleep(0.3)
        driver.find_element(By.ID, "sim-run").click()
        wait.until(lambda browser: "Breakpoint hit" in status(browser))

        driver.find_element(By.ID, "sim-terminal").click()
        terminal = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".xterm"))
        )
        terminal.click()
        driver.switch_to.active_element.send_keys("Z")

        if isinstance(driver, webdriver.Chrome):
            severe = [
                entry
                for entry in driver.get_log("browser")
                if entry.get("level") in {"SEVERE", "ERROR"}
            ]
            assert severe == []
    finally:
        if driver is not None:
            driver.quit()
        process.terminate()
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
