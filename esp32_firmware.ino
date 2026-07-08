#include <Adafruit_NeoPixel.h>

#define LED_PIN 48     // GPIO пин для данных WS2812B (измени под свою плату)
#define NUM_LEDS 256   // 16x16 = 256 светодиодов
#define BRIGHTNESS 150 // Яркость (0-255)

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
  Serial.begin(115200);
  strip.begin();
  strip.setBrightness(BRIGHTNESS);
  strip.clear();
  strip.show();
  Serial.println("READY");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "CLEAR") {
      // Очистить всю матрицу
      strip.clear();
      strip.show();
      Serial.println("OK");
    } else if (cmd == "SHOW") {
      // Обновить матрицу
      strip.show();
      Serial.println("OK");
    } else if (cmd.startsWith("BRIGHT:")) {
      // Установить яркость: BRIGHT:50
      int b = cmd.substring(7).toInt();
      strip.setBrightness(constrain(b, 0, 255));
      strip.show();
      Serial.println("OK");
    } else if (cmd.startsWith("P:")) {
      // Установить пиксель: P:index,R,G,B
      // Пример: P:0,255,0,0
      int firstComma = cmd.indexOf(',');
      int secondComma = cmd.indexOf(',', firstComma + 1);
      int thirdComma = cmd.indexOf(',', secondComma + 1);

      if (firstComma > 0 && secondComma > 0 && thirdComma > 0) {
        int idx = cmd.substring(2, firstComma).toInt();
        int r = cmd.substring(firstComma + 1, secondComma).toInt();
        int g = cmd.substring(secondComma + 1, thirdComma).toInt();
        int b = cmd.substring(thirdComma + 1).toInt();

        if (idx >= 0 && idx < NUM_LEDS) {
          strip.setPixelColor(idx, strip.Color(r, g, b));
          strip.show();
          Serial.println("OK");
        } else {
          Serial.println("ERR:IDX");
        }
      } else {
        Serial.println("ERR:FMT");
      }
    } else if (cmd.startsWith("FILL:")) {
      // Залить всю матрицу одним цветом: FILL:R,G,B
      int firstComma = cmd.indexOf(',');
      int secondComma = cmd.indexOf(',', firstComma + 1);

      if (firstComma > 0 && secondComma > 0) {
        int r = cmd.substring(5, firstComma).toInt();
        int g = cmd.substring(firstComma + 1, secondComma).toInt();
        int b = cmd.substring(secondComma + 1).toInt();

        strip.fill(strip.Color(r, g, b), 0, NUM_LEDS);
        strip.show();
        Serial.println("OK");
      }
    } else if (cmd.startsWith("BATCH:")) {
      // Пакетная отправка: BATCH:idx,R,G,B;idx,R,G,B;...
      // Не вызывает show() — для скорости
      String data = cmd.substring(6);
      int start = 0;
      while (start < data.length()) {
        int end = data.indexOf(';', start);
        if (end == -1)
          end = data.length();

        String pixel = data.substring(start, end);
        int c1 = pixel.indexOf(',');
        int c2 = pixel.indexOf(',', c1 + 1);
        int c3 = pixel.indexOf(',', c2 + 1);

        if (c1 > 0 && c2 > 0 && c3 > 0) {
          int idx = pixel.substring(0, c1).toInt();
          int r = pixel.substring(c1 + 1, c2).toInt();
          int g = pixel.substring(c2 + 1, c3).toInt();
          int bv = pixel.substring(c3 + 1).toInt();

          if (idx >= 0 && idx < NUM_LEDS) {
            strip.setPixelColor(idx, strip.Color(r, g, bv));
          }
        }
        start = end + 1;
      }
      strip.show();
      Serial.println("OK");
    } else {
      Serial.println("ERR:CMD");
    }
  }
}
