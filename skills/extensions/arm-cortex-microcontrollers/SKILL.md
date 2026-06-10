---
name: arm-cortex-microcontrollers
source: "wshobson/agents (adapted)"
version: "1.0"
description: >
  Expert guidance for ARM Cortex-M microcontroller development: peripheral configuration,
  interrupt handling, RTOS integration, low-power design, and bare-metal C/C++ firmware.
  Triggers: /arm-cortex-microcontrollers, arm cortex, microcontroller, embedded firmware,
  cortex-m, STM32, нужен микроконтроллер, встроенное ПО, прошивка.
triggers: [arm-cortex-microcontrollers, arm cortex, microcontroller, embedded firmware, cortex-m, STM32, bare-metal, RTOS, HAL, нужен микроконтроллер, встроенное ПО, прошивка]
tokens: ~2800
---

<!-- BSV
Скил   : arm-cortex-microcontrollers
TL;DR  : Разработка прошивок для ARM Cortex-M: периферия, прерывания, RTOS, низкое потребление
Вызов  : /arm-cortex-microcontrollers, arm cortex, microcontroller, встроенное ПО
НЕ для : высокоуровневого Linux-кода, веб-сервисов, облачных архитектур
-->

# ARM Cortex-M Microcontroller Development

Expert firmware development for ARM Cortex-M series (M0, M0+, M3, M4, M7, M33, M55).

## When to Use This Skill

- Configuring peripherals (GPIO, UART, SPI, I2C, ADC, DMA, timers)
- Writing interrupt service routines and NVIC configuration
- Integrating RTOS (FreeRTOS, Zephyr, RTX)
- Optimizing for low-power operation (sleep modes, clock gating)
- Debugging hard faults and memory corruption
- Linker script authoring and memory map planning
- Setting up toolchains (GCC ARM, LLVM, Keil, IAR)
- Writing portable HAL abstraction layers

## Core Capabilities

### 1. Peripheral Configuration

**GPIO**
```c
// STM32 HAL example — configure PA5 as push-pull output
GPIO_InitTypeDef GPIO_InitStruct = {0};
__HAL_RCC_GPIOA_CLK_ENABLE();
GPIO_InitStruct.Pin   = GPIO_PIN_5;
GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
GPIO_InitStruct.Pull  = GPIO_NOPULL;
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
```

**UART DMA transfer (non-blocking)**
```c
HAL_UART_Transmit_DMA(&huart2, tx_buf, len);
// Completion fires HAL_UART_TxCpltCallback
```

### 2. Interrupt Handling

- Always declare ISRs `void __attribute__((interrupt))` or match startup vector table names
- Keep ISRs short: set a flag, post to queue, then handle in task context
- Use `__DSB()` / `__ISB()` barriers after NVIC writes on Cortex-M3+
- Priority grouping: `NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_4)` — all bits for preemption, none for sub-priority

```c
void EXTI0_IRQHandler(void) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    vTaskNotifyGiveFromISR(sensor_task_handle, &xHigherPriorityTaskWoken);
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}
```

### 3. FreeRTOS Integration

- Stack overflow detection: `configCHECK_FOR_STACK_OVERFLOW 2`
- Heap: use `heap_4.c` for most embedded applications (coalescing free blocks)
- Always check return value of `xTaskCreate` — stack may be insufficient
- Use `configASSERT` liberally; strip in release with `NDEBUG`

```c
void sensor_task(void *pvParameters) {
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);  // Wait for ISR signal
        process_sensor_data();
    }
}
```

### 4. Low-Power Design

| Mode | Wake sources | Current (STM32L4 example) |
|---|---|---|
| Sleep | Any interrupt | ~1 mA |
| Stop 1 | RTC, EXTI, LPUART | ~5 µA |
| Stop 2 | RTC, EXTI | ~2 µA |
| Standby | RTC, WKUP pin | ~0.4 µA |
| Shutdown | WKUP pin | ~30 nA |

```c
// Enter Stop 2 — wake on RTC alarm
HAL_PWREx_EnterSTOP2Mode(PWR_STOPENTRY_WFI);
// Execution resumes here after wake
SystemClock_Config();  // Re-configure PLLs after wake
```

### 5. Hard Fault Debugging

```c
// Hard fault handler — dump registers via semihosting or UART
void HardFault_Handler(void) {
    __asm volatile (
        "TST   LR, #4      \n"
        "ITE   EQ          \n"
        "MRSEQ R0, MSP     \n"
        "MRSNE R0, PSP     \n"
        "B     hard_fault_handler_c \n"
    );
}

void hard_fault_handler_c(uint32_t *stack) {
    volatile uint32_t r0  = stack[0];
    volatile uint32_t pc  = stack[6];
    volatile uint32_t psr = stack[7];
    (void)r0; (void)pc; (void)psr;
    __BKPT(0);  // Halt debugger here
    for(;;);
}
```

### 6. Memory Map & Linker Scripts

```ld
MEMORY {
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
    CCMRAM(rwx) : ORIGIN = 0x10000000, LENGTH = 64K   /* STM32F4 core-coupled */
}

SECTIONS {
    .text : { *(.text*) } > FLASH
    .rodata : { *(.rodata*) } > FLASH
    .data : { *(.data*) } > RAM AT> FLASH
    .bss  : { *(.bss*) *(COMMON) } > RAM
    .ccmram : { *(.ccmram*) } > CCMRAM AT> FLASH
}
```

### 7. Toolchain Setup (GCC ARM)

```makefile
CC      = arm-none-eabi-gcc
CFLAGS  = -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
CFLAGS += -Os -g3 -Wall -Wextra
CFLAGS += -ffunction-sections -fdata-sections
LDFLAGS = -T STM32F429ZI_FLASH.ld --specs=nano.specs -Wl,--gc-sections
```

## Common Pitfalls

- **Cache coherency on M7**: flush/invalidate D-Cache before DMA transfers to/from shared buffers
- **Volatile is not atomic**: use `__LDREX`/`__STREX` or `atomic_*` for shared variables across ISR and task
- **Stack size underestimation**: add `configMINIMAL_STACK_SIZE` + printf/sprintf overhead + nested call depth
- **Clock not re-enabled after Stop mode**: always call `SystemClock_Config()` on wake
- **Floating-point in ISR**: ensure FPU context saving enabled (`FPU->FPCCR |= FPU_FPCCR_ASPEN_Msk`)

## Supported Families

| Family | Core | Typical use |
|---|---|---|
| STM32F0/G0 | M0/M0+ | Ultra-low-cost, simple control |
| STM32L4/L5 | M4/M33 | Low-power IoT |
| STM32F4/F7 | M4/M7 | Signal processing, motor control |
| STM32H7 | M7 | High-perf DSP, dual-core |
| nRF52/54 | M4/M33 | Bluetooth LE |
| RP2040 | M0+ dual | Maker boards, PIO |
| SAMD21/51 | M0+/M4 | Arduino ecosystem |

## Best Practices

1. Always configure watchdog (IWDG) in production firmware
2. Store calibration data in emulated EEPROM or dedicated flash page, not RAM
3. Use `__attribute__((section(".ccmram")))` for latency-critical buffers on F4/F7
4. Enable MPU to catch null-pointer dereferences and stack overflows early
5. Version your firmware image header (magic, version, CRC) for OTA validation
