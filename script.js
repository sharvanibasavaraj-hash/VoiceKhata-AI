import { PipecatClient } from "https://esm.sh/@pipecat-ai/client-js@1.16.0";
import { WebSocketTransport } from "https://esm.sh/@pipecat-ai/websocket-transport@1.8.1";

const API_BASE = "";
const AGENT_WS_URL = "ws://localhost:7860/ws-client";

const recordButton = document.getElementById("recordButton");
const stopButton = document.getElementById("stopButton");
const recordStatus = document.getElementById("recordStatus");
const languageSelect = document.getElementById("language");
const transcriptElement = document.getElementById("transcript");
const responseElement = document.getElementById("assistantResponse");
const notification = document.getElementById("notification");

let pcClient = null;
let connected = false;
let micEnabled = false;
let activeLanguage = null;
let ledgerRefreshTimer = null;

function showNotification(message) {
    notification.textContent = message;
    notification.classList.add("show");
}

function clearNotification() {
    notification.classList.remove("show");
}

function formatCurrency(amount) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0
    }).format(Number(amount) || 0);
}

function setConnectionStatus(online) {
    const status = document.querySelector(".status");
    const statusText = document.getElementById("connectionStatus");

    if (!status || !statusText) return;

    status.classList.toggle("online", online);
    status.classList.toggle("offline", !online);

    statusText.textContent = online
        ? "Server connected"
        : "Server disconnected";
}

async function loadLedger() {
    try {
        const response = await fetch(`${API_BASE}/api/ledger`);

        if (!response.ok) {
            throw new Error("Could not load ledger");
        }

        const data = await response.json();

        setConnectionStatus(true);

        document.getElementById("balance").textContent =
            formatCurrency(data.balance);

        document.getElementById("totalSales").textContent =
            formatCurrency(data.total_credit);

        document.getElementById("totalPurchases").textContent =
            formatCurrency(data.total_payments);

        renderTransactions(data.transactions || []);

    } catch (error) {
        console.error("Ledger error:", error);
        setConnectionStatus(false);
    }
}

function scheduleLedgerRefresh() {
    clearTimeout(ledgerRefreshTimer);

    ledgerRefreshTimer = setTimeout(() => {
        loadLedger();
    }, 500);
}

function renderTransactions(transactions) {
    const list = document.getElementById("transactionList");

    if (!transactions.length) {
        list.innerHTML =
            `<tr><td colspan="4" class="empty-state">No transactions recorded yet.</td></tr>`;
        return;
    }

    list.innerHTML = "";

    transactions.forEach(item => {
        const row = document.createElement("tr");

        const description = document.createElement("td");
        description.textContent = item.description || "Transaction";

        const type = document.createElement("td");
        type.textContent = String(item.type || "").toUpperCase();

        type.className =
            item.type === "credit" ? "type-sale" : "type-purchase";

        const amount = document.createElement("td");
        amount.textContent = formatCurrency(item.amount);

        const date = document.createElement("td");
        date.textContent = item.date || "-";

        row.append(description, type, amount, date);
        list.appendChild(row);
    });
}

function createVoiceClient() {
    return new PipecatClient({
        transport: new WebSocketTransport(),
        enableMic: true,
        enableCam: false,

        callbacks: {
            onConnected: () => {
                connected = true;
                setConnectionStatus(true);
                recordStatus.textContent = "Connected. Speak now.";
            },

            onDisconnected: () => {
                connected = false;
                micEnabled = false;

                setConnectionStatus(false);

                recordButton.disabled = false;
                stopButton.disabled = true;

                recordButton.classList.remove("recording");

                recordStatus.textContent =
                    "Tap the microphone to speak";
            },

            onBotReady: () => {
                responseElement.textContent =
                    "VoiceKhata is ready.";
            },

            onUserTranscript: data => {
                if (data?.final && data?.text) {
                    transcriptElement.textContent = data.text;
                }
            },

            onBotOutput: data => {
                if (data?.text) {
                    responseElement.textContent = data.text;
                    scheduleLedgerRefresh();
                }
            },

            onBotTtsText: data => {
                if (data?.text) {
                    responseElement.textContent = data.text;
                    scheduleLedgerRefresh();
                }
            },

            onError: error => {
                console.error("Pipecat client error:", error);

                showNotification(
                    error?.message || "Voice connection error."
                );
            }
        }
    });
}

async function disconnectVoiceClient() {
    try {
        if (pcClient) {
            if (micEnabled) {
                try {
                    await pcClient.enableMic(false);
                } catch (_) {}
            }

            try {
                await pcClient.disconnect();
            } catch (error) {
                console.warn("Disconnect warning:", error);
            }
        }
    } finally {
        pcClient = null;
        connected = false;
        micEnabled = false;
        activeLanguage = null;

        recordButton.disabled = false;
        stopButton.disabled = true;
        recordButton.classList.remove("recording");

        setConnectionStatus(false);
    }
}

async function startOrResumeMicrophone() {
    clearNotification();

    try {
        const selectedLanguage = languageSelect.value;

        if (!pcClient || !connected ||
            activeLanguage !== selectedLanguage) {

            if (pcClient) {
                await disconnectVoiceClient();
            }

            recordStatus.textContent =
                "Connecting in selected language...";

            recordButton.disabled = true;

            pcClient = createVoiceClient();

            // Pass the selected language to the Python agent.
            const wsUrl = new URL(AGENT_WS_URL);
            wsUrl.searchParams.set("language", selectedLanguage);

            await pcClient.connect({
                ws_url: wsUrl.toString()
            });

            activeLanguage = selectedLanguage;
            connected = true;
        }

        await pcClient.enableMic(true);

        micEnabled = true;

        recordButton.disabled = true;
        stopButton.disabled = false;

        recordButton.classList.add("recording");

        recordStatus.textContent =
            "Listening... tap Stop Recording when finished.";

    } catch (error) {
        console.error("Voice connection error:", error);

        recordButton.disabled = false;
        stopButton.disabled = true;

        recordStatus.textContent =
            "Could not connect to voice agent.";

        showNotification(
            error?.message ||
            "Could not connect. Check that agent.py is running."
        );

        await disconnectVoiceClient();
    }
}

async function stopMicrophone() {
    if (!pcClient || !connected || !micEnabled) return;

    try {
        await pcClient.enableMic(false);

        micEnabled = false;

        recordButton.classList.remove("recording");
        recordButton.disabled = false;
        stopButton.disabled = true;

        recordStatus.textContent =
            "Microphone stopped. You can start again.";

        scheduleLedgerRefresh();

    } catch (error) {
        console.error("Could not stop microphone:", error);
        showNotification("Could not stop the microphone cleanly.");
    }
}

async function submitCommand(event) {
    event.preventDefault();

    clearNotification();

    const input = document.getElementById("commandInput");
    const submitButton = document.getElementById("submitButton");

    const command = input.value.trim();

    if (!command) {
        showNotification("Please enter a transaction or question.");
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Processing...";

    try {
        const response = await fetch(`${API_BASE}/api/command`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                command: command,
                language: languageSelect.value
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Could not process command.");
        }

        transcriptElement.textContent = command;

        responseElement.textContent =
            data.reply || "Entry processed.";

        input.value = "";

        await loadLedger();

    } catch (error) {
        console.error("Command error:", error);
        showNotification(error.message);

    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Submit Entry";
    }
}

// If the language changes, close the old session.
// The next microphone start creates a session in the new language.
languageSelect.addEventListener("change", async () => {
    if (pcClient) {
        await disconnectVoiceClient();
    }

    transcriptElement.textContent =
        "Your voice transcript will appear here.";

    responseElement.textContent =
        "Language changed. Start speaking when ready.";

    recordStatus.textContent =
        "Language selected: " +
        languageSelect.options[languageSelect.selectedIndex].text;
});

recordButton.addEventListener("click", startOrResumeMicrophone);
stopButton.addEventListener("click", stopMicrophone);

document.getElementById("commandForm")
    .addEventListener("submit", submitCommand);

document.getElementById("refreshButton")
    .addEventListener("click", loadLedger);

window.addEventListener("beforeunload", () => {
    try {
        pcClient?.disconnect();
    } catch (_) {}
});
setInterval(loadLedger, 2000);
loadLedger();