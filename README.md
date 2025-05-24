`/boot/firmware/config.txt```
Underclock only if you ok with slow saving speed and you explicitly need more battery life. 

```
# camera
camera_auto_detect=1

# display
hdmi_force_hotplug=1
dtoverlay=vc4-kms-dsi-7inch,dsi1

# fast boot
boot_delay=0
disable_splash=1
arm_boost=1
initial_turbo=30

# powersave
arm_freq=800
arm_freq_min=500
over_voltage_delta=-2
gpu_freq=400
```
