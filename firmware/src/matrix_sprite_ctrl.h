#pragma once

#include <stdint.h>

#include <memory>
#include <string>
#include <vector>

#define PANEL_RES_X \
  64  // Number of pixels wide of each INDIVIDUAL panel module.
#define PANEL_RES_Y \
  32  // Number of pixels tall of each INDIVIDUAL panel module.

#define PANEL_ROW_BYTES (sizeof(Color565) * PANEL_RES_X)

/*
 *        +x (N)
 *        ^
 *        |
 *        |
 * -y <---+---> +y
 * (W)    |         (E)
 *        |
 *        v
 *        -x (S)
 */
static constexpr unsigned long MAX_FRAMES_PER_SEC = 24;

static constexpr unsigned long EFFECT_PERIOD_MS = 5000;

typedef uint16_t Color565;

class BaseSprite {
 public:
  BaseSprite() {}
  BaseSprite(const char* name, int x, int y, unsigned color, float speed = 0,
             unsigned offset_ms = 0)
      : name_(name),
        x_(x),
        y_(y),
        color_(color),
        speed_(speed),
        offset_ms_(offset_ms) {}
  virtual ~BaseSprite() {}

  virtual void Draw(size_t time_ms) const = 0;

  std::string name_;
  int x_ = 0;
  int y_ = 0;
  Color565 color_ = 0;
  float speed_ = 1;
  unsigned offset_ms_ = 0;
};

class PixelSprite : public BaseSprite {
 public:
  PixelSprite() {}
  PixelSprite(const char* name, int x, int y, unsigned color,
              unsigned end_color = 0, float speed = 1, unsigned offset_ms = 0)
      : BaseSprite(name, x, y, color, speed, offset_ms),
        end_color_(end_color) {}

  void Draw(size_t time_ms) const override;

  Color565 end_color_ = 0;
};

using SpritePtr = std::unique_ptr<BaseSprite>;

class MatrixSpriteController {
 public:
  static constexpr uint8_t DEFAULT_BRIGHTNESS = 128;
  void Init();

  void AddSprite(SpritePtr sprite);

  SpritePtr PopSprite(const char* name);
  SpritePtr PopSprite(const char* name, size_t length);

  void ClearSprites();

  void Draw();

  void SetBrightness(uint8_t brightness);

  void DrawBackground(const Color565* background_image);
  void DrawBackgroundRow(uint8_t row, const Color565* background_row);
  void SetBackgroundEnabled(bool enabled);

 private:
  unsigned long last_frame_time_ = 0;

  std::vector<SpritePtr> sprites_;
  uint8_t brightness_ = DEFAULT_BRIGHTNESS;
  bool draw_background_ = false;
  Color565 background_image_[PANEL_RES_X * PANEL_RES_Y] = {0};
  bool beginFrame();
};
