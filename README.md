

```
0 : imx477 [4056x3040 12-bit RGGB] (/base/axi/pcie@120000/rp1/i2c@80000/imx477@1a)
    Modes: 'SRGGB10_CSI2P' : 1332x990 [120.05 fps - (696, 528)/2664x1980 crop]
           'SRGGB12_CSI2P' : 2028x1080 [50.03 fps - (0, 440)/4056x2160 crop]
                             2028x1520 [40.01 fps - (0, 0)/4056x3040 crop]
                             4056x3040 [10.00 fps - (0, 0)/4056x3040 crop]
```


picamera2 library:
```
minimal exposure: 0
maximum exposure: 66666
```

```
sudo rm -rf LCD-show
git clone https://github.com/goodtft/LCD-show.git
chmod -R 755 LCD-show
cd LCD-show/
sudo ./LCD35-show
```
```
sudo sh -c "echo 2 > /sys/class/thermal/cooling_device0/cur_state"
```