#include <chrono>
#include <memory>
#include <string>
#include <cstring>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/float32.hpp"
#include "mini_agv_hardware/serialib.h"


//--------------- USER DEFINED -------------------
#define serial_port             "/dev/ttyUSB0"
#define serial_baudrate         115200
#define serial_timeout_sec      2.0
#define rx_callback_ms          1
#define tx_callback_ms          2

#pragma pack(push, 1)
struct rx_payload
{
    uint8_t driver_ready;
    int16_t enc_a_dt;
    int16_t enc_b_dt;
    uint8_t gpio;
    float   yaw_deg;
};
#pragma pack(pop)

#pragma pack(push, 1)
struct tx_payload
{
    uint8_t driver_start;
    uint8_t motor_start;
    int16_t motor_a_speed;
    int16_t motor_b_speed;
};
#pragma pack(pop)
//------------------------------------------------
enum ParserState
{
    WAITING_A,
    WAITING_B,
    WAITING_C,
    READING_PAYLOAD
};

class serial_node : public rclcpp::Node
{
private:
    serialib m_serial;
    rclcpp::Publisher<std_msgs::msg::Float32>::SharedPtr m_publisher;
    rclcpp::TimerBase::SharedPtr m_timer_rx;
    rclcpp::TimerBase::SharedPtr m_timer_tx;

    ParserState parse_state;
    int payload_bytes_read;
    double last_serial_rx;

    char rx_buffer[sizeof(rx_payload)];
    rx_payload rx_data;

    char tx_buffer[sizeof(tx_payload) + 3] = "ABC";
    tx_payload tx_data;

public:
    serial_node();
    ~serial_node();
    bool openSerial(const char* port, int baudrate);
    void restartSerial();
    void publishDataRx();
    bool processByteRx(char byte);
    void rx_callback();
    void tx_callback();
};


serial_node::serial_node()
: Node("serial_node"),
  parse_state(WAITING_A),
  payload_bytes_read(0),
  last_serial_rx(0.0),
  rx_data(),
  tx_data() 
{
    if (!openSerial(serial_port, serial_baudrate))
    {
        RCLCPP_ERROR(this->get_logger(), "Failed to open serial port! Shutting down.");
        rclcpp::shutdown();
        return;
    }

    m_publisher = this->create_publisher<std_msgs::msg::Float32>("serial_data", 10);

    m_timer_rx = this->create_wall_timer
    (
        std::chrono::milliseconds(rx_callback_ms),
        std::bind(&serial_node::rx_callback, this)
    );

    m_timer_tx = this->create_wall_timer
    (
        std::chrono::milliseconds(tx_callback_ms),
        std::bind(&serial_node::tx_callback, this)
    );

    last_serial_rx = this->now().seconds();
}

serial_node::~serial_node()
{
    m_serial.closeDevice();
    RCLCPP_INFO(this->get_logger(), "Serial port closed!");
}

bool serial_node::openSerial(const char* port, int baudrate)
{
    int ret = m_serial.openDevice(port, baudrate);
    if (ret == 1)
    {
        RCLCPP_INFO(this->get_logger(), "Serial port opened on %s at %d baud", port, baudrate);
        return true;
    }
    else
    {
        RCLCPP_ERROR(this->get_logger(), "openDevice() returned error %d", ret);
        return false;
    }
}

void serial_node::restartSerial()
{
    RCLCPP_WARN(this->get_logger(), "Restarting serial connection...");

    m_serial.closeDevice();

    if (openSerial(serial_port, serial_baudrate))
    {
        RCLCPP_INFO(this->get_logger(), "Serial connection restarted!");
    }
    else
    {
        RCLCPP_ERROR(this->get_logger(), "Serial restart failed!");
    }

    //--- Reset
    memset(&rx_data, 0, sizeof(rx_data));
    parse_state = WAITING_A;
    payload_bytes_read = 0;
    last_serial_rx = this->now().seconds();
}

void serial_node::publishDataRx()
{
    RCLCPP_INFO(this->get_logger(), "r,a,b,g,yaw: %d ; %d ; %d ; %d ; %.2f", rx_data.driver_ready, 
    rx_data.enc_a_dt, rx_data.enc_b_dt, rx_data.gpio, rx_data.yaw_deg);
    
    // auto msg = std_msgs::msg::Float32();
    // msg.header.stamp = this->now();
    // msg.header.frame_id = "serial_frame";
    // msg.data = rx_data.data1;
    // m_publisher->publish(msg);
}

//----------------------------------------------------------
//  parses one byte, returns true if a full
//  payload is ready (and data is extracted).
//----------------------------------------------------------
bool serial_node::processByteRx(char byte)
{
    bool payload_ready = false;

    switch (parse_state)
    {
        case WAITING_A:
            if (byte == 'A')
            {
                parse_state = WAITING_B;
            }
            break;

        case WAITING_B:
            if (byte == 'B')
            {
                parse_state = WAITING_C;
            }
            else
            {
                parse_state = WAITING_A;   // resync
            }
            break;

        case WAITING_C:
            if (byte == 'C')
            {
                parse_state = READING_PAYLOAD;
                payload_bytes_read = 0;
            }
            else
            {
                parse_state = WAITING_A;
            }
            break;

        case READING_PAYLOAD:
            rx_buffer[payload_bytes_read++] = byte;

            if (payload_bytes_read == sizeof(rx_buffer))
            {
                // Full payload received – extract data
                memcpy(&rx_data, rx_buffer, sizeof(rx_payload));
                payload_ready = true;
                parse_state = WAITING_A;
                payload_bytes_read = 0;
            }
            break;
    }

    return payload_ready;
}


void serial_node::rx_callback()
{
    if(this->now().seconds() - last_serial_rx > serial_timeout_sec)
    {
        restartSerial();
        return;
    }

    if (m_serial.available() <= 0)
    {
        return;
    }

    last_serial_rx = this->now().seconds();

    try
    {
        char byte;
        while (m_serial.available() > 0)
        {
            if (m_serial.readBytes(&byte, 1, 1, 1) != 1)
            {
                break;   // read failed, abort this cycle
            }
            if (processByteRx(byte))
            {
                publishDataRx();
            }
        }
    }
    catch (...)
    {
        RCLCPP_ERROR(this->get_logger(), "Exception in serial parsing!");
        //--- Reset
        memset(&rx_data, 0, sizeof(rx_data));
        parse_state = WAITING_A;
        payload_bytes_read = 0;
    }
}

void serial_node::tx_callback()
{
    tx_data.driver_start = 1;
    tx_data.motor_start = 1;
    tx_data.motor_a_speed = 0;
    tx_data.motor_b_speed = 5;

    memcpy(tx_buffer + 3, &tx_data.driver_start, 1);
    memcpy(tx_buffer + 4, &tx_data.motor_start, 1);
    memcpy(tx_buffer + 5, &tx_data.motor_a_speed, 2);
    memcpy(tx_buffer + 7, &tx_data.motor_b_speed, 2);

    for(size_t i = 0; i < sizeof(tx_buffer); i++)
    {
        if(m_serial.isDeviceOpen())
        {
            try
            {
                m_serial.writeChar(tx_buffer[i]);
            }
            catch(...)
            {
                RCLCPP_WARN(this->get_logger(), "Unable to transmit serial!");
            }
        }
    }
}

int main(int argc, char const *argv[])
{
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<serial_node>());
    rclcpp::shutdown();
    return 0;
}