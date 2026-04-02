// =================【配置参数】=================
const int X1_VAL = 698;   // 位置1：引脚5高电平目标值
const int X2_VAL = 2360;  // 位置2：引脚21高电平目标值 (原引脚6功能)
const int X3_VAL = 1581;  // 位置3：释放或按BOOT键回到的目标值

const int TOLERANCE = 80; // 模拟量容差

const int PIN_0  = 0;
const int PIN_1  = 1;  // AS5600 模拟量引脚
const int PIN_5  = 5;
const int PIN_9  = 9;  // BOOT 键
const int PIN_10 = 10; // 电机控制 A
const int PIN_20 = 20; // 电机控制 B 
const int PIN_21 = 21; // 复合功能引脚 (位置2控制 + 0引脚触发)
// ==============================================

// 状态追踪
bool last_pin5 = LOW;
bool last_pin21 = HIGH;
bool last_boot = HIGH;

// 引脚 0 定时器
bool is_pin0_active = false;
unsigned long pin0_start_time = 0;

// 目标状态机
int current_target = -1; 

// 辅助函数：电机控制
void motorRun() {
  digitalWrite(PIN_20, HIGH);
  digitalWrite(PIN_10, LOW);
}

void motorStop() {
  digitalWrite(PIN_20, HIGH);
  digitalWrite(PIN_10, HIGH);
}

void setup() {
  // 保持串口关闭，确保引脚控制权
  pinMode(PIN_0, OUTPUT);
  pinMode(PIN_10, OUTPUT);
  pinMode(PIN_20, OUTPUT);
  
  pinMode(PIN_5, INPUT_PULLDOWN);
  pinMode(PIN_21, INPUT_PULLUP); // 21号引脚建议上拉
  pinMode(PIN_9, INPUT_PULLUP);  // BOOT 键硬件上拉

  digitalWrite(PIN_0, LOW);
  motorStop(); 

  // 初始化状态同步
  delay(50);
  last_pin5 = digitalRead(PIN_5);
  last_pin21 = digitalRead(PIN_21);
  last_boot = digitalRead(PIN_9);
}

void loop() {
  unsigned long current_millis = millis();
  
  int current_analog = analogRead(PIN_1);
  bool pin5_state = digitalRead(PIN_5);
  bool pin21_state = digitalRead(PIN_21);
  bool boot_state = digitalRead(PIN_9);

  // --------------------------------------------------------
  // 逻辑 1：引脚 21 下降沿触发 (双重任务)
  // --------------------------------------------------------
  if (last_pin21 == HIGH && pin21_state == LOW) {
    // 任务 A：触发引脚 0 拉高 5 秒
    is_pin0_active = true;
    pin0_start_time = current_millis;
    digitalWrite(PIN_0, HIGH);

    // 任务 B：触发电机前往位置 3
    current_target = X3_VAL;
  }

  // 引脚 0 定时器处理
  if (is_pin0_active) {
    if (current_millis - pin0_start_time >= 5000) {
      digitalWrite(PIN_0, LOW);
      is_pin0_active = false;
    }
  }

  // --------------------------------------------------------
  // 逻辑 2：其他下降沿触发 (引脚 5 和 BOOT)
  // --------------------------------------------------------
  if (last_pin5 == HIGH && pin5_state == LOW) {
    current_target = X3_VAL;
  }
  if (last_boot == HIGH && boot_state == LOW) {
    current_target = X3_VAL;
  }

  // --------------------------------------------------------
  // 逻辑 3：优先级判断与目标覆盖 (5 > 21 > 回位置3)
  // --------------------------------------------------------
  if (pin5_state == HIGH) {
    current_target = X1_VAL; // 优先级最高
  } 
  else if (pin21_state == HIGH) {
    // 当 21 为高电平且 5 为低电平时，目标为位置 2
    // 注意：如果你的开关是接地的，按下时为低，不按时为高，则上电会自动去位置 2
    current_target = X2_VAL; 
  }
  else if (pin5_state == LOW && pin21_state == LOW && current_target != X3_VAL) {
    // 两个控制引脚都为低，且当前没有回位置 3 的任务，则停机
    current_target = -1;
  }

  // --------------------------------------------------------
  // 逻辑 4：电机执行层
  // --------------------------------------------------------
  if (current_target != -1) {
    if (abs(current_analog - current_target) <= TOLERANCE) {
      motorStop();
      if (current_target == X3_VAL) {
        current_target = -1; 
      }
    } else {
      motorRun();
    }
  } else {
    motorStop();
  }

  // 更新状态
  last_pin5 = pin5_state;
  last_pin21 = pin21_state;
  last_boot = boot_state;
}
