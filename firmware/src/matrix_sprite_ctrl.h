#pragma once

#include <vector>
#include <memory>
#include <stdint.h>

class BaseSprite
{
public:
   BaseSprite() {}
   BaseSprite(int x, int y, unsigned color, unsigned speed = 0) : x_(x), y_(y), color_(color), speed_(speed) {}
   virtual ~BaseSprite() {}

   virtual void Draw(size_t cycles) const = 0;

   int x_ = 0;
   int y_ = 0;
   // RGBA each 8-bit
   uint32_t color_ = 0;
   unsigned speed_ = 0;
};

class PixelSprite : public BaseSprite
{
public:
   PixelSprite() {}
   PixelSprite(int x, int y, unsigned color, unsigned end_color = 0, unsigned speed = 0) : BaseSprite(x, y, speed, color), end_color_(end_color) {}

   void Draw(size_t cycles) const override;

   // RGBA each 8-bit
   uint32_t end_color_ = 0;
};

using SpritePtr = std::unique_ptr<BaseSprite>;

class MatrixSpriteController
{
public:
   static constexpr uint8_t DEFAULT_BRIGHTNESS = 90;
   void Init();

   void AddSprite(SpritePtr &sprite);

   void Draw();

   void SetBrightness(uint8_t brightness);

private:
   std::vector<SpritePtr> sprites_;
   uint8_t brightness_ = DEFAULT_BRIGHTNESS;
};
