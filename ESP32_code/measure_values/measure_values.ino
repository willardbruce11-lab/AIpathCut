// =================【配置参数】=================
const int X1_VAL   = 698;   // 位置1：引脚5高电平时停转目标值
const int X2_VAL   = 2360;  // 位置2：引脚6高电平时停转目标值
const int X3_VAL   = 1581;  // 位置3：5或6释放后回到的目标值
const int TOLERANCE = 30;   // 模拟量容差

const int PIN_0  = 0;
const int PIN_1  = 1;
const int PIN_5  = 5;
const int PIN_6  = 6;
const int PIN_10 = 10;
const int PIN_20 = 20;
const int PIN_21 = 21;
// ==============================================

bool last_pin5  = LOW;
bool last_pin6  = LOW;
bool last_pin21 = HIGH;

bool          is_pin0_active   = false;
unsigned long pin0_start_time  = 0;

bool is_returning_to_x3 = false;

void motorRun() {
  digitalWrite(PIN_20, HIGH);
  digitalWrite(PIN_10, LOW);
}

void motorStop() {
  digitalWrite(PIN_20, HIGH);
  digitalWrite(PIN_10, HIGH);
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_0,  OUTPUT);
  pinMode(PIN_10, OUTPUT);
  pinMode(PIN_20, OUTPUT);
  pinMode(PIN_5,  INPUT_PULLDOWN);
  pinMode(PIN_6,  INPUT_PULLDOWN);
  pinMode(PIN_21, INPUT_PULLUP);

  digitalWrite(PIN_0, LOW);
  motorStop();
}

void loop() {
  unsigned long current_millis = millis();

  int  current_analog = analogRead(PIN_1);
  bool pin5_state     = digitalRead(PIN_5);
  bool pin6_state     = digitalRead(PIN_6);
  bool pin21_state    = digitalRead(PIN_21);

  // ── 引脚21下降沿 → 引脚0拉高5秒 ──────────────────
  if (last_pin21 == HIGH && pin21_state == LOW) {
    is_pin0_active  = true;
    pin0_start_time = current_millis;
    digitalWrite(PIN_0, HIGH);
  }
  if (is_pin0_active && current_millis - pin0_start_time >= 5000) {
    digitalWrite(PIN_0, LOW);
    is_pin0_active = false;
  }
  last_pin21 = pin21_state;

  // ── 检测5/6下降沿 → 触发回位X3任务 ───────────────
  if (last_pin5 == HIGH && pin5_state == LOW) {
    is_returning_to_x3 = true;
  }
  if (last_pin6 == HIGH && pin6_state == LOW && pin5_state == LOW) {
    is_returning_to_x3 = true;
  }

  // ── 电机状态机 ────────────────────────────────────
  if (pin5_state == HIGH) {
    is_returning_to_x3 = false;
    if (abs(current_analog - X1_VAL) > TOLERANCE) {
      motorRun();
    } else {
      motorStop();
    }
  }
  else if (pin6_state == HIGH) {
    is_returning_to_x3 = false;
    if (abs(current_analog - X2_VAL) > TOLERANCE) {
      motorRun();
    } else {
      motorStop();
    }
  }
  else if (is_returning_to_x3) {
    if (abs(current_analog - X3_VAL) > TOLERANCE) {
      motorRun();
    } else {
      motorStop();
      is_returning_to_x3 = false;
    }
  }
  else {
    motorStop();
  }

  last_pin5 = pin5_state;
  last_pin6 = pin6_state;
}
