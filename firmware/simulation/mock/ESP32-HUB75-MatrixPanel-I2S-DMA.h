#pragma once
#include <stdint.h>

#include <cstdio>

typedef uint16_t Color565;

namespace sf {
class RenderWindow;
class Texture;
class Sprite;
class RenderTexture;
}  // namespace sf

struct HUB75_I2S_CFG {
  struct i2s_pins {
    int r1, g1, b1, r2, g2, b2, a, b, c, d, e, lat, oe, clk;
  };
  HUB75_I2S_CFG(int w, int h, int c, i2s_pins p) : width(w), height(h) {}
  int width, height;
  bool clkphase;
  bool double_buff;
};

class MatrixPanel_I2S_DMA {
 public:
  static constexpr int COLS = 64;
  static constexpr int ROWS = 32;

  MatrixPanel_I2S_DMA(HUB75_I2S_CFG cfg);

  void begin();
  void setBrightness8(uint8_t b);

  void clearScreen();

  void drawPixel(int x, int y, uint16_t color);

  void drawRGBBitmap(int x, int y, const uint16_t* bitmap, int w, int h);

  void flipDMABuffer();

  static void update();

  static bool isOpen();

 private:
  static sf::RenderWindow* window_;
  static sf::Texture* overlayTexture_;
  static sf::Sprite* overlaySprite_;
  static sf::RenderTexture* ledLayer_;
  static bool redraw_;
};