document.addEventListener("DOMContentLoaded", function() {
    const themeSwitch = document.getElementById("theme-switch");
    const video = document.getElementById('video');
    const statusElem = document.getElementById('status');
    const connectBtn = document.getElementById('connect');
    const screenImage = document.getElementById('screen');
    
    const serverAddress = 'vaflya.local';
    const serverPort = 4500;
    
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

    function setupSlider(id, displayId) {
        let slider = document.getElementById(id);
        let display = document.getElementById(displayId);

        if(slider && display) {
            slider.addEventListener("input", () => {
                display.innerText = Number(slider.value).toFixed(2);
                console.log(id + ": " + slider.value);
            });
        }
    }

    // setupSlider("explosure", "explosureVal");
    // setupSlider("gain", "gainVal");
    // setupSlider("redGain", "redGainVal");
    // setupSlider("blueGain", "blueGainVal");
    // setupSlider("shutterSpeed1", "shutterSpeed1Val");
    // setupSlider("shutterSpeed2", "shutterSpeed2Val");

    const redGain = document.getElementById("redGain")
    redGain.addEventListener("change", async () => {
        const redGainValue = redGain.value;
        document.getElementById("redGainVal").textContent = redGainValue;
        const payload = {
            value: redGainValue
        }

        try {
            const response = await fetch('http://vaflya.local:4500/red_gain', {
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

    const blueGain = document.getElementById("blueGain")
    blueGain.addEventListener("change", async () => {
        const blueGainValue = blueGain.value;
        document.getElementById("blueGainVal").textContent = blueGainValue;
        const payload = {
            value: blueGainValue
        }

        try {
            const response = await fetch('http://vaflya.local:4500/blue_gain', {
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



    const analogueGain = document.getElementById("gain")
    analogueGain.addEventListener("change", async () => {
        const gainValue = analogueGain.value;
        document.getElementById("gainVal").textContent = gainValue;
        const payload = {
            value: gainValue
        }

        try {
            const response = await fetch('http://vaflya.local:4500/analogue_gain', {
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
        document.getElementById("shutterSpeed1Val").textContent = exposureValue;
        const payload = {
            value: Math.floor(exposureValue * 1_000_000)
        };
    
        try {
            const response = await fetch('http://vaflya.local:4500/exposure_time', {
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

    const exposure2 = document.getElementById("shutterSpeed2");
    exposure.addEventListener("change", async () => {
        const exposureValue2 = exposure2.value;
        document.getElementById("shutterSpeed2Val").textContent = exposureValue2;
        const payload = {
            value: Math.floor(exposureValue2 * 1_000_000)
        };

        try {
            const response = await fetch('http://vaflya.local:4500/exposure_time', {
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


    

    // const resolutionSelect = document.getElementById("resolution");
    // if (resolutionSelect) {
    //     resolutionSelect.addEventListener("change", function() {
    //         console.log("Resolution: " + this.value);
    //     });
    //

    const captureButton = document.getElementById("capture");
    if (captureButton) {
        captureButton.addEventListener("click", async function() {
            try {
                const response = await fetch('http://vaflya.local:4500/capture', {
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