# Edge Hill University — Smart Vending Machine System

A modular, robust, and accessible smart vending machine software system developed in Python and Tkinter for the Software Engineering group assignment.

---

## 🏛️ System Architecture

The project adopts a clean **Model-View-Controller (MVC) / Layered Architecture** with strict Separation of Concerns (SoC):

```text
VendingMachine/
├── main.py                     # Primary Application Entry Point
├── requirements.txt            # Python Dependencies
├── README.md                   # System Documentation
│
├── src/                        # Core Application Source Package
│   ├── controllers/            # [Controller Layer] Application Orchestration & State Machine
│   │   ├── __init__.py
│   │   └── controller.py       # VendingMachineController, JSON Loaders & Savers
│   │
│   ├── models/                 # [Domain Layer] Business Logic & Hardware Entities
│   │   ├── __init__.py
│   │   ├── inventory.py        # Drink, DrinkDispenser, StockSensor, LoyaltyAccount
│   │   ├── payment.py          # PaymentModule, CashReceiver, CashValidator, ChangeDispenser
│   │   └── bank.py             # BankService Interface, MockBankService
│   │
│   ├── views/                  # [Presentation Layer] User Interface & Camera Feeds
│   │   ├── __init__.py
│   │   ├── customer_ui.py      # Tkinter GUI, Customer Flow, Admin Options Dashboard
│   │   └── barcode_scanner.py  # OpenCV & Pyzbar Live Camera Barcode Scanner
│   │
│   └── utils/                  # [Cross-Cutting Layer] Shared Utilities
│       ├── __init__.py
│       ├── timer.py            # TransactionTimer (Countdown & Timeout)
│       └── logger.py           # Logger & TransactionRecord
│
├── data/                       # [Persistence Layer] JSON Databases
│   ├── activity_log.json       # System Event & Hardware Diagnostic Logs
│   ├── cash_inventory.json     # Coin & Banknote Quantities & Capacities
│   ├── members.json            # Loyalty Member Accounts & Discount Rates
│   ├── payment_config.json     # Gateway Configurations & Payment Method Toggles
│   ├── products.json           # Product Catalogue, Pricing, Weight & Dimensions
│   └── transactions.json       # Order & Transaction Receipts
│
└── assets/                     # [Static Assets] High-Resolution Product Photos & Logos
    ├── edge_hill_logo.png
    └── *.jpg / *.png / *.avif
```

---

## 🎨 UI Color Palette (Strict 5-Color Theme)

| Color Name | Hex Code | Usage |
| :--- | :--- | :--- |
| **Deep Aubergine Purple** | `#3A0C51` | Primary background, headers, management tab typography |
| **Electric Lime Green** | `#BAEF2D` | Primary CTAs, active selections, price tags |
| **Pure White** | `#FFFFFF` | Card surfaces, modal containers, high-contrast text |
| **Bright Lavender Lilac** | `#D883FF` | Secondary accents, status text, subtitles |
| **Deep Forest Green** | `#12372E` | Digital terminal displays, numpad button backgrounds |

---

## 🚀 Getting Started

### 1. Prerequisites & Installation
Ensure Python 3.9+ is installed, then install requirements:
```bash
pip install -r requirements.txt
```

### 2. Launching the Application
Run the primary entry point:
```bash
python3 main.py
```

---

## 🔒 Cash & Payment Acceptance Rules
- **Accepted Denominations (10p to £10.00):**
  - Coins: `10p`, `20p`, `50p`, `£1.00`, `£2.00`
  - Banknotes: `£5.00 Note`, `£10.00 Note`
- **Rejection Policy:**
  - Banknotes of `£20.00` and `£50.00`, as well as coins below `10p`, are rejected by the validator and mechanically returned to the customer without incrementing the total inserted.
- **Dynamic Gateways:**
  - Supports switching between Stripe (Dynamic QR), PayPal REST, Custom REST, and Mock Bank.
