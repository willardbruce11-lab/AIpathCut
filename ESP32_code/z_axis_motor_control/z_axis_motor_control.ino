// =================【配置参数】=================
const int X1_VAL = 698;   // 位置1：引脚5高电平目标值
const int X2_VAL = 2360;  // 位置2：引脚21高电平目标值 (M4)
const int X3_VAL = 1581;  // 位置3：引脚21低电平目标值 (M3 / 默认)

const int TOLERANCE = 80; // 模拟量容差

const int PIN_0  = 0;
const int PIN_1  = 1;  // AS5600 模拟量引脚
const int PIN_5  = 5;
const int PIN_9  = 9;  // BOOT 键
const int PIN_10 = 10; // 电机控制 A
const int PIN_20 = 20; // 电机控制 B 
const int PIN_21 = 21; // GRBL 信号输入
// ==============================================

bool last_pin21 = LOW;
bool is_pin0_active = false;
unsigned long pin0_start_time = 0;

void motorRun() {
  digitalWrite(PIN_20, HIGH);
  digitalWrite(PIN_10, LOW);
}

void motorStop() {
  digitalWrite(PIN_20, HIGH);
  digitalWrite(PIN_10, HIGH);
}

void setup() {
  pinMode(PIN_0, OUTPUT);
  pinMode(PIN_10, OUTPUT);
  pinMode(PIN_20, OUTPUT);
  
  pinMode(PIN_5, INPUT_PULLDOWN);
  pinMode(PIN_21, INPUT_PULLDOWN); 
  pinMode(PIN_9, INPUT_PULLUP);    

  digitalWrite(PIN_0, LOW);
  motorStop(); 

  delay(50);
  last_pin21 = digitalRead(PIN_21);
}

void loop() {
  unsigned long current_millis = millis();
  
  // 简单平均滤波：读三次取平均，防止电机启动瞬间的毛刺导致提前刹车
  int current_analog = (analogRead(PIN_1) + analogRead(PIN_1) + analogRead(PIN_1)) / 3;
  
  bool pin5_state = digitalRead(PIN_5);
  bool pin21_state = digitalRead(PIN_21);
  bool boot_state = digitalRead(PIN_9);

  // --------------------------------------------------------
  // 逻辑 A：独立的引脚 0 下降沿触发 (5秒定时)
  // --------------------------------------------------------
  if (last_pin21 == HIGH && pin21_state == LOW) {
    is_pin0_active = true;
    pin0_start_time = current_millis;
    digitalWrite(PIN_0, HIGH);
  }

  if (is_pin0_active) {
    if (current_millis - pin0_start_time >= 5000) {
      digitalWrite(PIN_0, LOW);
      is_pin0_active = false;
    }
  }
  last_pin21 = pin21_state;

  // --------------------------------------------------------
  // 逻辑 B：绝对电平目标映射 (指哪打哪)
  // --------------------------------------------------------
  int current_target = -1;

  if (pin5_state == HIGH) {
    current_target = X1_VAL; // 最高优先级：按住 5，去位置 1
  } 
  else if (pin21_state == HIGH) {
    current_target = X2_VAL; // 只要 21 是高电平，死死锁定位置 2
  } 
  else {
    current_target = X3_VAL; // 只要 21 是低电平，死死锁定位置 3
  }

  // BOOT 键特殊处理：因为低电平时默认就是去 X3，所以 BOOT 键的作用
  // 是在引脚 21 为高电平 (在位置 2) 时，强行覆盖去位置 3。
  if (boot_state == LOW) {
    current_target = X3_VAL; 
  }

  // --------------------------------------------------------
  // 逻辑 C：无脑执行层
  // --------------------------------------------------------
  // 只要没进容差圈，就一直给我转！
  if (abs(current_analog - current_target) <= TOLERANCE) {
    motorStop(); 
  } else {
    motorRun();
  }
}
