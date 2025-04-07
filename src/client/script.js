document.addEventListener("DOMContentLoaded", function() {
    const themeSwitch = document.getElementById("theme-switch");
    const serverAddress = 'vaflya.local';
    themeSwitch.addEventListener("change", function() {
        if(this.checked) {
            document.body.classList.remove("dark-theme");
            document.body.classList.add("light-theme");
            localStorage.setItem("theme", "light");
        } else {
            document.body.classList.remove("light-theme");
            document.body.classList.add("dark-theme");
            localStorage.setItem("theme", "dark");
        }
    });

    const savedTheme = localStorage.getItem("theme");
    if(savedTheme === "light") {
        themeSwitch.checked = true;
        document.body.classList.remove("dark-theme");
        document.body.classList.add("light-theme");
    }
    
    const redGain = document.getElementById("redGain");
    redGain.addEventListener("change", async () => {
        const redGainValue = redGain.value;
        document.getElementById("redGainVal").textContent = redGainValue;
        const payload = {
            value: redGainValue
        };
        try {
            const response = await fetch(`http://${serverAddress}:4500/red_gain`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            console.error("Request failed:", error);
        }
    });

    const blueGain = document.getElementById("blueGain");
    blueGain.addEventListener("change", async () => {
        const blueGainValue = blueGain.value;
        document.getElementById("blueGainVal").textContent = blueGainValue;
        const payload = {
            value: blueGainValue
        };
        try {
            const response = await fetch(`http://${serverAddress}:4500/blue_gain`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            console.error("Request failed:", error);
        }
    });

    const analogueGain = document.getElementById("gain");
    analogueGain.addEventListener("change", async () => {
        const gainValue = analogueGain.value;
        document.getElementById("gainVal").textContent = gainValue;
        const payload = {
            value: gainValue
        };
        try {
            const response = await fetch(`http://${serverAddress}:4500/analogue_gain`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            console.error("Request failed:", error);
        }
    });

    const exposure = document.getElementById("shutterSpeed1");
    exposure.addEventListener("change", async () => {
        const exposureValue = exposure.value;
        const payload = {
            value: Math.log(exposureValue*0.3 + 1) * 1_000_000
        };
        document.getElementById("shutterSpeed1Val").textContent = payload.value.toFixed(0);
        try {
            const response = await fetch(`http://${serverAddress}:4500/exposure_time`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });
        } catch (error) {
            console.error("Request failed:", error);
        }
    });

    const captureButton = document.getElementById("capture");
    if (captureButton) {
        captureButton.addEventListener("click", async function() {
            try {
                const response = await fetch(`http://${serverAddress}:4500/capture`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                });
            } catch (error) {
                console.error("Request failed:", error);
            }
        });
    }

});