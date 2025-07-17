## Firebase Mono Currency

### **Description:**
The main goal of the project is to request currency exchange rates from Mono by Firebase Functions every 3 hours and store them into Firebase Firestore

### **Deploy:**
```bash
firebase deploy
```
### **Run locally (emulator):**
```bash
firebase emulators:start
```

### **Trigger Firebase Functions locally:**
```bash
firebase functions:shell
```
```bash
firebase > populate_currencies()
firebase > fetch_and_store_data()
```
