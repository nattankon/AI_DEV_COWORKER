# Cowork UX/UI Rebuild Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with test and visual-review checkpoints. Do not reuse the current Cowork layout except for transport and persistence contracts.

**Goal:** สร้าง Cowork desktop workspace ใหม่จากศูนย์ ให้ใช้งานคล่องแบบ coding agent terminal ผสมความเป็นมิตรของ desktop assistant โดยใช้โครงสร้าง Local AI, IPC และ session persistence ที่มีอยู่

**Architecture:** UI ใหม่เป็น feature-contained React workspace ภายใต้ `frontend/` ของ project root `C:\AI_DEV_COWORKER` แยก state, components, views และ adapters ออกจากกันอย่างชัดเจน UI รับข้อมูลผ่าน Cowork bridge interface เดียว ไม่ import host bridge กระจายตาม component และไม่ใส่ agent business logic ไว้ใน presentation components

**Relocation note:** แผนนี้เดิมเขียนก่อนย้ายโปรเจกต์ออกจาก `C:\API-BLENDER`. Paths ภายในแผนนี้เป็น relative paths จาก `C:\AI_DEV_COWORKER`; paths ของ host ระบุเป็น absolute paths เท่านั้น

**Status note:** Checklist ด้านล่างเก็บลำดับงานเดิมไว้เป็น implementation reference; สถานะที่ทำเสร็จแล้วและ next action ให้ยึด `PROJECT_STATE.md` กับ `work_logs/WORK_LOG.md` เป็นหลัก

**Tech Stack:** React 19, Electron, Vite, Tailwind CSS, Lucide React, Python sidecar, LM Studio OpenAI-compatible API

---

## 1. Product Direction

### สิ่งที่เก็บไว้

- Local AI provider และ model identifier
- Python Cowork runtime และ tool-calling loop
- Electron-to-Python IPC transport
- การเลือก working directory
- JSONL session records และ conversation recovery
- Host compatibility export ที่ทำให้แอปหลักเรียก Cowork ได้

### สิ่งที่จะสร้างใหม่

- Information architecture ทั้งหมดของ Cowork
- Component tree และ frontend state model
- Session navigation และ project workspace
- Message/task timeline
- Tool activity, approval, diff และ verification surfaces
- Composer และ command interactions
- Settings สำหรับ provider/model/context
- Empty, loading, error, offline และ recovery states

### แนวทางภาพและประสบการณ์

- ใช้ความหนาแน่นและความรวดเร็วแบบ Codex CLI แต่ไม่จำลอง terminal ทั้งหน้าจอ
- ใช้ความชัดเจนและ approachable interaction แบบ Claude App แต่ไม่คัดลอกแบรนด์หรือ layout
- Cowork ต้องดูเป็นเครื่องมือพัฒนาโปรแกรม ไม่ใช่ chatbot ทั่วไป
- เน้นข้อความ โค้ด diff สถานะ และหลักฐาน มากกว่าการ์ดตกแต่ง
- Dark neutral palette พร้อม accent สีเดียวของ Cowork; หลีกเลี่ยง gradient และ glow ที่ไม่สื่อความหมาย
- รองรับ keyboard-first workflow แต่ทุก action สำคัญต้องกดด้วยเมาส์ได้

## 2. Target Screen Structure

```text
┌──────────────┬────────────────────────────────┬──────────────────┐
│ Sessions     │ Task / Conversation Timeline   │ Context / Changes│
│ Projects     │                                │ Model / Tools    │
│ New task     │ Tool calls                     │ Approval / Diff  │
│ History      │ Assistant responses            │ Verification     │
│              │                                │                  │
│ Account-free │ Composer + attachments         │ Run summary      │
└──────────────┴────────────────────────────────┴──────────────────┘
```

Responsive behavior:

- Width 1200px ขึ้นไป: แสดงสามคอลัมน์
- Width 800-1199px: ซ่อน inspector เป็น drawer
- ต่ำกว่า 800px: sessions และ inspector เป็น overlays; timeline และ composer เป็นแกนหลัก
- ห้ามเกิด horizontal page overflow ที่ 800px, 1024px, 1280px และ 1440px

## 3. Frontend File Map

สร้างหรือปรับไฟล์ดังนี้:

```text
frontend/
├── CoworkApp.jsx                 # feature root and state composition
├── index.js                      # public exports only
├── adapters/
│   ├── coworkBridge.js           # single interface to Electron/Python bridge
│   └── sessionStorage.js         # renderer cache and migration
├── components/
│   ├── AppHeader.jsx             # project/model/run status
│   ├── SessionRail.jsx           # sessions and project navigation
│   ├── Timeline.jsx              # ordered task events
│   ├── TimelineEntry.jsx         # event router
│   ├── MessageEntry.jsx          # user/assistant content
│   ├── ToolCallEntry.jsx         # tool status, args, result summary
│   ├── ApprovalCard.jsx          # allow/deny write or command
│   ├── DiffViewer.jsx            # file diff presentation
│   ├── VerificationCard.jsx      # test/lint/build results
│   ├── Composer.jsx              # prompt, command, attachments
│   ├── ContextInspector.jsx      # model, workspace, budget, capabilities
│   ├── EmptyWorkspace.jsx        # first-run actions
│   └── StatusBanner.jsx          # offline/error/recovery states
├── hooks/
│   ├── useCoworkBridge.js        # subscriptions and commands
│   ├── useCoworkSession.js       # reducer and session lifecycle
│   └── useComposerShortcuts.js   # keyboard interaction
├── model/
│   ├── coworkEvents.js           # event types and validators
│   ├── coworkReducer.js          # deterministic UI state transitions
│   └── coworkSelectors.js        # derived display data
├── styles/
│   └── cowork.css                # feature tokens and layout rules
└── tests/
    ├── coworkReducer.test.js
    ├── sessionStorage.test.js
    ├── Timeline.test.jsx
    ├── ApprovalCard.test.jsx
    └── Composer.test.jsx
```

ไฟล์ host ที่แก้ได้เฉพาะ integration:

```text
C:\API-BLENDER\frontend\src\features\cowork\index.js
C:\API-BLENDER\frontend\src\App.jsx
C:\API-BLENDER\frontend\electron\main.js
C:\API-BLENDER\frontend\electron\preload.cjs
C:\API-BLENDER\frontend\src\lib\eel.js
```

## 4. State And Event Contract

UI ใช้ event envelope เดียว:

```js
{
  id: "event-id",
  sessionId: "session-id",
  timestamp: "2026-06-12T00:00:00.000Z",
  type: "message.assistant",
  status: "complete",
  payload: {}
}
```

Event types รุ่นแรก:

```text
session.started
session.finished
message.user
message.assistant
message.system
agent.status
tool.started
tool.finished
tool.failed
approval.requested
approval.resolved
diff.proposed
verification.started
verification.finished
error
```

UI reducer ต้อง deterministic: event sequence เดียวกันต้องได้ state เดียวกัน และ session history ต้อง replay จาก JSONL ได้

## 5. Implementation Tasks

### Task 1: Freeze Core Contracts

**Files:**

- Create: `frontend/model/coworkEvents.js`
- Create: `frontend/tests/coworkEvents.test.js`
- Modify: `ARCHITECTURE.md`

- [ ] ระบุ event envelope และ event types ตามหัวข้อ 4
- [ ] เพิ่ม validator ที่ปฏิเสธ event ซึ่งไม่มี `id`, `sessionId`, `timestamp`, `type` หรือ `payload`
- [ ] เขียน test สำหรับ valid event, missing field และ unknown event type
- [ ] รัน `npm test -- coworkEvents.test.js` และต้องผ่านทั้งหมด
- [ ] บันทึกผลใน `work_logs/WORK_LOG.md`

### Task 2: Introduce A Single Bridge Adapter

**Files:**

- Create: `frontend/adapters/coworkBridge.js`
- Create: `frontend/hooks/useCoworkBridge.js`
- Modify: `C:\API-BLENDER\frontend\src\lib\eel.js`
- Test: `frontend/tests/coworkBridge.test.js`

- [ ] สร้าง interface `sendPrompt`, `selectWorkspace`, `answerApproval`, `subscribe`, `getConnectionState`
- [ ] แปลง event รูปแบบเดิม `cowork_log` และ `cowork_ui_state` เป็น event envelope ใน adapter
- [ ] ห้าม presentation component import `eel.js` โดยตรง
- [ ] ทดสอบ unsubscribe, duplicate events และ malformed payload
- [ ] ตรวจว่า Designer และ Builder ไม่ได้รับผลกระทบ

### Task 3: Build Deterministic Session State

**Files:**

- Create: `frontend/model/coworkReducer.js`
- Create: `frontend/model/coworkSelectors.js`
- Create: `frontend/hooks/useCoworkSession.js`
- Test: `frontend/tests/coworkReducer.test.js`

- [ ] สร้าง initial state สำหรับ session, events, run status, approvals และ changed files
- [ ] รองรับ event replay จาก JSONL-derived data
- [ ] ป้องกัน duplicate event ด้วย `event.id`
- [ ] สร้าง selectors สำหรับ timeline, pending approvals, changed files และ verification summary
- [ ] ทดสอบ session replay และ out-of-order event handling

### Task 4: Create The New Workspace Shell

**Files:**

- Create: `frontend/CoworkApp.jsx`
- Create: `frontend/components/AppHeader.jsx`
- Create: `frontend/components/SessionRail.jsx`
- Create: `frontend/components/ContextInspector.jsx`
- Create: `frontend/styles/cowork.css`
- Modify: `frontend/index.js`

- [ ] ลบ dependency ต่อ layout ของ prototype `CoworkPanel.jsx`
- [ ] สร้าง three-region layout ตามหัวข้อ 2
- [ ] กำหนด feature CSS variables สำหรับ background, surface, border, text, accent, success, warning และ error
- [ ] แสดง connection, workspace, model และ run status จาก state จริงเท่านั้น
- [ ] ทดสอบ desktop, compact และ narrow breakpoints

### Task 5: Build Timeline Rendering

**Files:**

- Create: `frontend/components/Timeline.jsx`
- Create: `frontend/components/TimelineEntry.jsx`
- Create: `frontend/components/MessageEntry.jsx`
- Create: `frontend/components/ToolCallEntry.jsx`
- Test: `frontend/tests/Timeline.test.jsx`

- [ ] Render user, assistant, system และ tool events ต่างรูปแบบกัน
- [ ] Tool entries แสดงชื่อ tool, status, duration และ result summary
- [ ] ซ่อน arguments/result ยาวไว้หลัง disclosure control
- [ ] รองรับ code block, inline code, list และ plain text โดยไม่ใช้ raw HTML
- [ ] Auto-scroll เฉพาะเมื่อผู้ใช้อยู่ใกล้ท้าย timeline

### Task 6: Build The Command-First Composer

**Files:**

- Create: `frontend/components/Composer.jsx`
- Create: `frontend/hooks/useComposerShortcuts.js`
- Test: `frontend/tests/Composer.test.jsx`

- [ ] `Ctrl+Enter` ส่ง prompt และ `Shift+Enter` ขึ้นบรรทัดใหม่
- [ ] แสดง workspace และ model ที่กำลังใช้ก่อนส่ง
- [ ] รองรับ command suggestions รุ่นแรก: `/new`, `/history`, `/model`, `/workspace`, `/clear`
- [ ] ปิดการส่งเมื่อ offline, busy หรือ prompt ว่าง
- [ ] รักษา draft เมื่อสลับ inspector/session rail

### Task 7: Add Durable Session Navigation

**Files:**

- Create: `frontend/adapters/sessionStorage.js`
- Modify: `frontend/components/SessionRail.jsx`
- Modify: `session_store.py`
- Test: `frontend/tests/sessionStorage.test.js`
- Test: `test/test_session_store.py`

- [ ] แสดง sessions จาก disk-backed store ไม่พึ่ง account chat history
- [ ] รองรับเปิด session เก่า, สร้าง session ใหม่ และตั้งชื่อ session
- [ ] เก็บ renderer draft แยกตาม session ID
- [ ] เพิ่ม schema version และ migration สำหรับ local cache
- [ ] ทดสอบ corrupt JSONL และ partial final line โดยไม่ทำให้แอปล่ม

### Task 8: Add Approval And Diff Surfaces

**Files:**

- Create: `frontend/components/ApprovalCard.jsx`
- Create: `frontend/components/DiffViewer.jsx`
- Modify: `frontend/model/coworkReducer.js`
- Test: `frontend/tests/ApprovalCard.test.jsx`

- [ ] Approval แสดง action, target path, risk, reason และ proposed diff
- [ ] มี `Allow once`, `Deny` และ `Always allow for this session` เฉพาะ policy ที่อนุญาต
- [ ] ปุ่มอนุมัติต้อง disable หลังตอบเพื่อป้องกัน double submission
- [ ] Diff แสดง added/removed lines และ file summary
- [ ] UI ต้องไม่ระบุว่าเขียนสำเร็จก่อนรับ `tool.finished`

### Task 9: Add Verification And Completion Evidence

**Files:**

- Create: `frontend/components/VerificationCard.jsx`
- Modify: `frontend/components/ContextInspector.jsx`
- Modify: `frontend/model/coworkSelectors.js`

- [ ] แสดง command, exit code, duration และ stdout/stderr summary
- [ ] แยกสถานะ passed, failed, skipped และ unavailable
- [ ] Run summary ต้องแสดง files changed, approvals, tools, tests และ unresolved risks
- [ ] Completion badge แสดงได้เมื่อมี `session.finished` และไม่มี pending approval

### Task 10: Model And Provider Settings

**Files:**

- Create: `frontend/components/ModelMenu.jsx`
- Modify: `frontend/components/AppHeader.jsx`
- Modify: `frontend/components/ContextInspector.jsx`

- [ ] แสดง provider, model, context, local/cloud และ model-loaded state
- [ ] Local เป็นค่าเริ่มต้น
- [ ] Cloud selection ต้องแสดง privacy notice ก่อนใช้งานครั้งแรก
- [ ] ห้ามแสดง API keys ใน UI หรือ logs
- [ ] แสดง actionable error เมื่อ LM Studio server หรือ model ไม่พร้อม

### Task 11: Accessibility And Responsive Review

**Files:**

- Modify: files under `frontend/components/`
- Modify: `frontend/styles/cowork.css`

- [ ] ทุก interactive control มี accessible name
- [ ] Focus order: session rail -> header -> timeline controls -> composer -> inspector
- [ ] Contrast ผ่าน WCAG AA สำหรับข้อความหลักและ controls
- [ ] Keyboard สามารถเปิด/ปิด drawers และตอบ approval ได้
- [ ] Browser verification ที่ 800x700, 1024x768, 1280x720 และ 1440x900
- [ ] ไม่มี console errors และไม่มี horizontal overflow

### Task 12: Electron Integration And Regression Verification

**Files:**

- Modify only if required: `C:\API-BLENDER\frontend\electron\main.js`
- Modify only if required: `C:\API-BLENDER\frontend\electron\preload.cjs`
- Modify only if required: `C:\API-BLENDER\frontend\src\App.jsx`
- Update: `PROJECT_STATE.md`
- Append: `work_logs/WORK_LOG.md`

- [ ] เปิด Electron shell และเลือก `local:qwen/qwen3.5-9b`
- [ ] เลือก workspace และส่ง prompt
- [ ] ยืนยัน message, tool event และ final response แสดงตามลำดับ
- [ ] ปิดและเปิดแอปใหม่ แล้ว session ต้องกลับมา
- [ ] ทดสอบ Designer และ Builder ขั้นพื้นฐานเพื่อยืนยัน host regression ไม่มี
- [ ] รัน Python compile, frontend tests และ production build

## 6. Delivery Milestones

### Milestone A: Usable Chat Workspace

Tasks 1-7 เสร็จ: มี shell ใหม่, timeline, composer และ durable sessions โดยยังใช้ tools เดิมแบบ read-oriented

### Milestone B: Safe Coding Workspace

Tasks 8-9 เสร็จ: มี approval, diff และ verification evidence พร้อมเชื่อม Permission Gate

### Milestone C: Production-Ready Desktop Experience

Tasks 10-12 เสร็จ: provider settings, responsive/accessibility และ Electron regression verification ครบ

## 7. Definition Of Done

- UI ใหม่ไม่ reuse layout/component ของ prototype เดิม
- Cowork business logic อยู่ใน `cowork_feature`
- Session เปิดกลับได้โดยไม่อาศัยบัญชีหรือ chat thread ภายนอก
- Tool, approval, diff และ verification มี event/state ที่ตรวจสอบย้อนหลังได้
- Local model เป็นค่าเริ่มต้นและ cloud เป็น opt-in
- Production build, tests และ Electron smoke workflow ผ่าน
- Designer และ Builder ของแอปหลักยังทำงาน
- `PROJECT_STATE.md` และ `WORK_LOG.md` ถูกอัปเดตพร้อมหลักฐาน verification
