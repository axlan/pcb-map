#include "matrix_sprite_ctrl.h"

#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>


#define PANEL_RES_X 64      // Number of pixels wide of each INDIVIDUAL panel module. 
#define PANEL_RES_Y 32     // Number of pixels tall of each INDIVIDUAL panel module.
#define PANEL_CHAIN 1      // Total number of panels chained one to another
 
//MatrixPanel_I2S_DMA dma_display;
static MatrixPanel_I2S_DMA *dma_display = nullptr;

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
#define E_PIN -1 // required for 1/32 scan panels, like 64x64px. Any available pin would do, i.e. IO32
#define LAT_PIN 15
#define OE_PIN 13
#define CLK_PIN 12

static HUB75_I2S_CFG::i2s_pins panel_pins={R1_PIN, G1_PIN, B1_PIN, R2_PIN, G2_PIN, B2_PIN, A_PIN, B_PIN, C_PIN, D_PIN, E_PIN, LAT_PIN, OE_PIN, CLK_PIN};

void MatrixSpriteController::Init() {
  // Module configuration
  HUB75_I2S_CFG mxconfig(
    PANEL_RES_X,   // module width
    PANEL_RES_Y,   // module height
    PANEL_CHAIN    // Chain length
    ,panel_pins
  );

  // mxconfig.double_buff = true;
  // mxconfig.min_refresh_rate = 30;

  //mxconfig.gpio.e = 18;
  mxconfig.clkphase = false;
  //mxconfig.driver = HUB75_I2S_CFG::FM6126A;

  // Display Setup
  dma_display = new MatrixPanel_I2S_DMA(mxconfig);
  dma_display->begin();
  dma_display->setBrightness8(brightness_); //0-255
  dma_display->clearScreen();
}

void MatrixSpriteController::SetBrightness(uint8_t brightness)
{
  brightness_ = brightness;
  if (dma_display != nullptr) {
    dma_display->setBrightness8(brightness_);
  }
}
