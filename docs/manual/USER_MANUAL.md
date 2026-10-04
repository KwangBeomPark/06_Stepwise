# 📘 Stepwise User Manual

*Read in other languages: [English](USER_MANUAL.md) | [Polski (Polska)](USER_MANUAL.pl.md) | [한국어](USER_MANUAL.ko.md)*

---

## 💡 1. What is Stepwise? (30-Second Summary)

**Stepwise** is a reliable desktop automation assistant designed for enterprise offices and factories. It eliminates tedious, repetitive data entry by reading rows from an Excel or CSV spreadsheet and automatically typing them into enterprise software (such as SAP GUI, ERP, legacy desktop software, or internal web portals) using mouse and keyboard controls.

### ❓ How is Stepwise different from generic macros or heavy RPA?

| Feature | Generic Keyboard/Mouse Macro | Stepwise Automation |
| :--- | :--- | :--- |
| **System or Network Lag** | Blindly clicks without checking, causing **misclicks, wrong fields, or crashes** | Uses visual computer vision (`Guard`) to verify the screen state before clicking |
| **On Unexpected Error** | Continues blindly, causing **data loss, missing records, or duplicates** | Stops immediately (`Fail-Fast`) and pinpoints the exact failure reason |
| **Excel Source File** | May overwrite or corrupt the original spreadsheet | **Never modifies your original data file**; writes execution logs to a separate CSV |
| **Emergency Stop** | Difficult to interrupt; users often resort to power buttons | Instant stop within 0.01 seconds by pressing **F12** |
| **Admin Permissions** | Requires IT administrative privileges to install | Runs out-of-the-box with **standard user permissions (No Admin required)** |

---

## 🚀 2. 5-Minute Quick Start Guide (Your First Automation)

New to Stepwise? Follow this simple tutorial to connect an Excel spreadsheet and build your first automated workflow in 5 minutes!

```
[ Quick Workflow ]
1. Open Excel Data  ➡️  2. Understand 3 Sections  ➡️  3. Add Click & Type  ➡️  4. Run & Verify
```

### Step 1: Open Your Excel Data File
1. In the top toolbar or the right-side **[Data Preview]** tab, click **[Choose Data File...]**.
2. Select your `.xlsx` or `.csv` spreadsheet file (e.g., columns: `VendorCode`, `ItemNumber`, `Quantity`, `UnitPrice`).
3. Your data will immediately display in the preview table below, and blue clickable tags like `[+ {VendorCode}]` and `[+ {Quantity}]` will appear at the top.

---

### Step 2: Understand the 3-Section Pipeline
In the center Action Tree, you will notice three main sections:

1. **📁 SETUP (Runs once at the start)**:
   - Actions to prepare the environment (e.g., bring the ERP window to the front, enter a transaction T-Code, or navigate to the search screen).
2. **📁 PER ROW (Repeats for every data row)**:
   - **The core pipeline.** Steps placed here will execute sequentially for row 1, row 2, row 3, etc. This is where your repetitive clicking, typing, and submitting take place.
3. **📁 CLEANUP (Runs once at the end)**:
   - Finalizing steps executed after all rows finish (e.g., closing the transaction screen, saving summary notes, or notifying completion).

---

### Step 3: Add Mouse Clicks and Text Input

#### ① Click into an Input Field
1. Click the **[+ Click]** button at the bottom-left of the Action Tree.
2. A new click action is created in `PER ROW`.
3. In the right **[Properties]** panel, click **[Pick (F8)]**.
4. Your mouse cursor turns into a red crosshair. **Click the target input box on your ERP screen**. The exact X and Y coordinates are filled in automatically!

#### ② Type Data from the Excel Spreadsheet
1. Click the **[+ Type]** button at the bottom-left.
2. In the right **[Properties]** panel, click into the `Text to type:` input field.
3. Click the blue `[+ {VendorCode}]` button from the variable list. `{VendorCode}` is inserted instantly.
4. *Tip*: You can mix variables with fixed text, such as `{VendorCode} - AutoOrder`.

#### ③ Press Enter or Tab
1. To move to the next field, click **[+ Key]** and select `Tab` or `Enter`.

---

### Step 4: Run and Test Emergency Stop

1. Click the green **[▶ Run]** button on the top toolbar (or press **F5**).
2. Stepwise will begin reading row 1 of your spreadsheet, clicking the screen, and typing the data automatically.
3. **🚨 Emergency Stop (F12)**:
   - If you ever need to stop the automation immediately, simply press **`F12`** on your keyboard.
   - All actions cease within 0.01 seconds without waiting or hanging.

---

## 🛡️ 3. Built-in Safety Features (Guard & Verify)

Enterprise systems frequently encounter slow network responses, loading spinners, or error dialogs. Stepwise protects your data integrity with visual checks:

### 1) Guard (Pre-Check): "Verify the window is open before clicking!"
- In the action's Properties panel, check **`[✓] Enable Guard`**.
- Click **[Capture (F9)]** to freeze your screen.
- **Drag a rectangle over a unique icon or window title** that confirms the screen is ready.
- **Result**: Stepwise will check the screen for this image before attempting the action. If the system is still loading, it waits. If it times out, it halts safely.

### 2) Verify (Post-Check): "Confirm data was saved before moving to the next row!"
- On your final "Save" or "Submit" click action, check **`[✓] Enable Verify`**.
- Click **[Capture (F9)]** and capture the success message or toast (e.g., *"Document saved successfully"*).
- **Result**: Stepwise ensures the transaction was accepted by your system before proceeding to the next spreadsheet row.

---

## 📊 4. Batch Execution & Results Preservation

Running hundreds of records unattended is safe and transparent.

1. **Original File Protection**:
   - Stepwise treats your original Excel file as strictly read-only. It never modifies or locks your source data.
2. **Real-time Result CSV**:
   - As each row processes, a timestamped result file (`results_<filename>_<timestamp>.csv`) is saved to disk immediately.
   - Every row records `SUCCESS`, `FAILED`, execution duration, and exact failure notes.
3. **Resume Failed Rows Only**:
   - If an unexpected dialog caused row 45 to stop, close the dialog, right-click row 45 in Data Preview, and choose **[Retry this row]** or **[Run from this row]**. You never need to start over from row 1.

---

## ⚡ 5. Speed Tuning & Best Practices

### 1) Dealing with Network Lag
- Use the quick speed toggle in the top toolbar:
  - **Normal**: Standard optimized execution speed (Recommended).
  - **Slow (+0.5s)**: Adds 0.5s safety delay between every step.
  - **Very slow (+1.0s)**: Adds 1.0s delay for severe network or server delays.

### 2) Screen Resolution & Window Placement
- Keep the target application window in a consistent position (e.g., maximized or snapped to a specific monitor).
- The bottom status bar in Stepwise automatically shows whether your current screen resolution and DPI match the macro's recorded state (e.g., `1920x1080 @100% ✅`).

---

## ❓ Frequently Asked Questions (FAQ)

**Q1. Should I store passwords in macro steps?**  
> ⚠️ **Never.** For corporate compliance and security, do not store plain-text passwords in macro files. Please log in to your ERP or system manually before starting Stepwise.

**Q2. Foreign characters or special symbols are not typing correctly.**  
> In the `+ Type` properties panel, change the **Typing mode** to **`Paste (Clipboard)`**. Stepwise uses the Windows Clipboard to reliably enter Unicode text across all languages (Polish, Korean, German, Chinese, etc.).

**Q3. Can I use my computer for other work while Stepwise is running?**  
> Because Stepwise drives the physical keyboard and mouse, moving your mouse during execution may disrupt coordinate clicks. We recommend letting Stepwise run while you enjoy a short break or work on a secondary laptop!
