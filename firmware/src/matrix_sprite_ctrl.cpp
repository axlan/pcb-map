#include "matrix_sprite_ctrl.h"

#include <Arduino.h>
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>

#include <algorithm>
#include <cstring>

#define PANEL_CHAIN 1  // Total number of panels chained one to another

static constexpr unsigned long FRAME_INTERVAL = 1000UL / MAX_FRAMES_PER_SEC;

// MatrixPanel_I2S_DMA dma_display_s;
static MatrixPanel_I2S_DMA* dma_display_s = nullptr;

// Panel Pin Wiring
#define R1_PIN 19
#define G1_PIN 5
#define B1_PIN 23
#define R2_PIN 25
#define G2_PIN 17
#define B2_PIN 26
#define A_PIN 27
#define B_PIN 16
#define C_PIN 14
#define D_PIN 4
#define E_PIN \
  -1  // required for 1/32 scan panels, like 64x64px. Any available pin would
      // do, i.e. IO32
#define LAT_PIN 15
#define OE_PIN 13
#define CLK_PIN 12

static constexpr HUB75_I2S_CFG::i2s_pins PANEL_PINS = {
    R1_PIN, G1_PIN, B1_PIN, R2_PIN, G2_PIN,  B2_PIN, A_PIN,
    B_PIN,  C_PIN,  D_PIN,  E_PIN,  LAT_PIN, OE_PIN, CLK_PIN};

static Color565 Interpolate565(Color565 start, Color565 end, float progress) {
  // Extract 5-bit red (bits 15-11), 6-bit green (bits 10-5), 5-bit blue (bits
  // 4-0)
  uint8_t r1 = (start >> 11) & 0x1F;
  uint8_t g1 = (start >> 5) & 0x3F;
  uint8_t b1 = start & 0x1F;

  uint8_t r2 = (end >> 11) & 0x1F;
  uint8_t g2 = (end >> 5) & 0x3F;
  uint8_t b2 = end & 0x1F;

  // Linearly interpolate each channel
  uint8_t r = static_cast<uint8_t>(r1 + (r2 - r1) * progress);
  uint8_t g = static_cast<uint8_t>(g1 + (g2 - g1) * progress);
  uint8_t b = static_cast<uint8_t>(b1 + (b2 - b1) * progress);

  // Repack into RGB565
  return (static_cast<Color565>(r) << 11) | (static_cast<Color565>(g) << 5) |
         static_cast<Color565>(b);
}

// static void DrawTestPattern() {
//   dma_display_s->fillScreen(0xFFFF);
//   delay(500);
//   // fix the screen with green
//   dma_display_s->fillRect(0, 0, dma_display_s->width(), dma_display_s->height(), dma_display_s->color444(0, 15, 0));
//   delay(500);
//   // draw a box in yellow
//   dma_display_s->drawRect(0, 0, dma_display_s->width(), dma_display_s->height(), dma_display_s->color444(15, 15, 0));
//   delay(500);
//   // draw an 'X' in red
//   dma_display_s->drawLine(0, 0, dma_display_s->width()-1, dma_display_s->height()-1, dma_display_s->color444(15, 0, 0));
//   dma_display_s->drawLine(dma_display_s->width()-1, 0, 0, dma_display_s->height()-1, dma_display_s->color444(15, 0, 0));
//   delay(500);
//   // draw a blue circle
//   dma_display_s->drawCircle(10, 10, 10, dma_display_s->color444(0, 0, 15));
//   delay(500);
//   // fill a violet circle
//   dma_display_s->fillCircle(40, 21, 10, dma_display_s->color444(15, 0, 15));
//   delay(500);
// }

void MatrixSpriteController::Init() {
  // Module configuration
  HUB75_I2S_CFG mxconfig(PANEL_RES_X,  // module width
                         PANEL_RES_Y,  // module height
                         PANEL_CHAIN   // Chain length
                         ,
                         PANEL_PINS);

  // mxconfig.double_buff = true;
  // mxconfig.min_refresh_rate = 30;

  // mxconfig.gpio.e = 18;
  mxconfig.clkphase = false;
  // mxconfig.driver = HUB75_I2S_CFG::FM6126A;

  // Display Setup
  dma_display_s = new MatrixPanel_I2S_DMA(mxconfig);
  dma_display_s->begin();
  dma_display_s->setBrightness8(brightness_);  // 0-255
  dma_display_s->clearScreen();
}

bool MatrixSpriteController::beginFrame() {
  unsigned long now = millis();
  if (now - last_frame_time_ < FRAME_INTERVAL) return false;
  last_frame_time_ = now;
  return true;
}

void MatrixSpriteController::Draw() {
  if (!beginFrame()) return;

  auto now = millis();
  if (draw_background_) {
     dma_display_s->drawRGBBitmap(0, 0, background_image_, PANEL_RES_X,
                                 PANEL_RES_Y);
  } else {
    dma_display_s->clearScreen();
  }

  // Logic for drawing sprites. When multiple sprites occupy the same location,
  // cycle through the one to display.
  // TODO: Only do this if they're the same type?
  // Make static to reduce dynamic memory churn
  static std::vector<bool> processed;
  static std::vector<size_t> collisions;

  processed.resize(sprites_.size());
  std::fill(processed.begin(), processed.end(), false);

  for (size_t i = 0; i < sprites_.size(); i++) {
    if (processed[i]) continue;

    collisions.clear();
    collisions.push_back(i);
    processed[i] = true;

    for (size_t c = i + 1; c < sprites_.size(); c++) {
      if (processed[c]) continue;
      const auto& a = sprites_[i];
      const auto& b = sprites_[c];
      if (a->x_ == b->x_ && a->y_ == b->y_) {
        collisions.push_back(c);
        processed[c] = true;
      }
    }

    size_t display_idx = (now / EFFECT_PERIOD_MS) % collisions.size();
    sprites_[collisions[display_idx]]->Draw(now);
  }
}

void MatrixSpriteController::SetBrightness(uint8_t brightness) {
  brightness_ = brightness;
  if (dma_display_s != nullptr) {
    dma_display_s->setBrightness8(brightness_);
  }
}

void MatrixSpriteController::DrawBackground(const Color565* background_image) {
  memcpy(background_image_, background_image, sizeof(background_image_));
  draw_background_ = true;
}

void MatrixSpriteController::DrawBackgroundRow(uint8_t row,
                                               const Color565* background_row) {
  if (row >= PANEL_RES_Y) return;
  memcpy(&background_image_[row * PANEL_RES_X], background_row,
         PANEL_ROW_BYTES);
}

void MatrixSpriteController::SetBackgroundEnabled(bool enabled) {
  draw_background_ = enabled;
}

void MatrixSpriteController::AddSprite(SpritePtr sprite) {
  auto it = std::find_if(
      sprites_.begin(), sprites_.end(),
      [&](const SpritePtr& elem) { return elem->name_ == sprite->name_; });

  if (it != sprites_.end()) {
    std::swap(*it, sprite);
  } else {
    sprites_.emplace_back(std::move(sprite));
  }
}

SpritePtr MatrixSpriteController::PopSprite(const char* name, size_t length) {
  auto it = std::find_if(
      sprites_.begin(), sprites_.end(), [&](const SpritePtr& elem) {
        return elem->name_.size() == length &&
               strncmp(elem->name_.c_str(), name, length) == 0;
      });
  if (it == sprites_.end()) {
    return SpritePtr();
  }

  auto sprite = std::move(*it);
  sprites_.erase(it);
  return sprite;
}

SpritePtr MatrixSpriteController::PopSprite(const char* name) {
  return PopSprite(name, strlen(name));
}

void MatrixSpriteController::ClearSprites() { sprites_.clear(); }

void PixelSprite::Draw(size_t time_ms) const {
  time_ms += offset_ms_;
  float cycle = float(time_ms % size_t(EFFECT_PERIOD_MS / speed_)) /
                (float(EFFECT_PERIOD_MS) / speed_);
  // Triangle wave: goes 0->1 then 1->0
  float progress = (cycle < 0.5f) ? (2.0f * cycle) : (2.0f * (1.0f - cycle));
  Color565 cur_color = Interpolate565(color_, end_color_, progress);
  dma_display_s->drawPixel(x_, y_, cur_color);
}
