# Drive-Thru Discrete Event Simulation

This project implements **Project Title No. 2: Discrete Event Simulation of a Drive-Thru Service System for Performance Optimization** from the provided documentation.

The system models a drive-thru service flow with:

- Vehicle arrivals following a random Poisson-style arrival process.
- FIFO movement through order placement, payment, food pickup, and departure.
- Adjustable order stations, payment windows, pickup windows, peak-hour demand, and lane capacity.
- Queue congestion detection when the drive-thru lane is full.
- Performance metrics for waiting time, throughput, service-window utilization, and bottlenecks.
- A generated analysis box that concludes whether each scenario is good, acceptable, or needs improvement.
- Real-world improvement suggestions based on congestion, bottlenecks, waiting time, and utilization.
- A simple 2D desktop UI that animates vehicles moving through the service system.

## Project Structure

- `drive_thru_model.py` - SimPy-based discrete event simulation model.
- `app.py` - Tkinter 2D user interface and scenario runner.
- `requirements.txt` - Python dependency list.
- `proposal_extracted.txt` - Extracted reference text from the provided PDF.

## Setup

If SimPy is already installed, you can skip setup and run the project directly.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python app.py
```

## Suggested Scenarios

Baseline:

- 24-hour simulation duration, or `1440` minutes
- 12 arrivals per hour
- Lunch/afternoon peak window from `660` to `840` minutes, or 11:00 AM to 2:00 PM
- 1 order station
- 1 payment window
- 1 pickup window
- Lane capacity of 10 vehicles

Peak-hour test:

- Increase peak multiplier to `2.5` or `3.0`
- Keep one service point per stage
- Observe queue buildup, rejected vehicles, and bottleneck stage

Optimization test:

- Add one more order station or pickup window
- Rerun the same arrival settings
- Compare average queue wait, throughput, and utilization

## Modeling Notes

The initial service-time assumptions follow the documentation:

- Order placement: 1-3 minutes
- Payment: 30-60 seconds
- Food pickup: 1-2 minutes

Food preparation delay is incorporated into the pickup service time, matching the initial assumption that preparation may be included unless modeled separately.
