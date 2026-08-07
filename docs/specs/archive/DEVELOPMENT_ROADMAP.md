# AI Dev Co-worker: Local-First Development Roadmap

เอกสารนี้แปลงแนวคิดจากบทความต้นฉบับให้เป็นแผนพัฒนาที่ลงมือทำได้จริง โดยยึดโค้ดปัจจุบันใน project root `C:\AI_DEV_COWORKER` และเครื่องพัฒนา RTX 5060 VRAM 8GB เป็นฐาน

## 1. เป้าหมายผลิตภัณฑ์

สร้าง AI Dev Co-worker ที่ทำงานกับ repository ในเครื่องได้อย่างปลอดภัย เข้าใจบริบทของโปรเจกต์ วางแผน แก้โค้ด เรียกเครื่องมือตรวจสอบ และรายงานผลโดยมีหลักฐาน โดยใช้ Local AI เป็นค่าเริ่มต้นและรองรับ Cloud AI เป็นทางเลือก

หลักการตัดสินใจ:

- Local-first: โค้ดและข้อมูลโปรเจกต์ไม่ออกจากเครื่องโดยไม่จำเป็น
- Safety before autonomy: เพิ่มสิทธิ์ให้ Agent หลังมี Permission Gate, Audit Log และ Test เท่านั้น
- Evidence before completion: ห้ามรายงานว่างานสำเร็จหากยังไม่มีผลตรวจสอบล่าสุด
- Small reversible changes: ทุกการเขียนไฟล์ต้องดู diff และย้อนกลับได้
- Measure before adding complexity: ยังไม่เพิ่ม LangGraph, Vector DB หรือ LoRA จนกว่าจะมีข้อมูลชี้ว่าจำเป็น

## 2. สถานะปัจจุบัน

สิ่งที่มีแล้ว:

- Backend Cowork แยกอยู่ในโมดูล Python ที่ project root
- CLI แบบติดตั้งเป็นคำสั่ง `cowork` ทำงานเดี่ยวโดยไม่พึ่งโปรแกรมเดิม
- Frontend Cowork แยกอยู่ใน `frontend/`
- เชื่อมต่อ LM Studio ผ่าน OpenAI-compatible API ได้
- เลือกโมเดลด้วย namespace `local:<model-id>` ได้
- Agent เรียกเครื่องมืออ่าน เขียน ค้นหา และแสดงรายการไฟล์ได้
- Workspace path guard ปฏิเสธ traversal และ absolute path ภายนอก
- Secret Guard ปิดกั้น `.env`, private keys และ credential stores ก่อน list/search/read/write
- การเขียนไฟล์มี diff, approval และ atomic replacement
- โมเดลหลักปัจจุบัน `qwen/qwen3.5-9b` สามารถเรียก tool และอ่านไฟล์จริงได้
- มีหน่วยความจำ Markdown ขั้นต้น

ช่องว่างสำคัญ:

- ยังไม่มี rollback backup
- ยังไม่มี evaluation set และ completion gate
- ยังไม่มี Git tools, test runner แบบ allowlist, repository map หรือ structured memory
- JSONL มี session และ tool events แล้ว แต่ approval audit ยังต้องละเอียดขึ้น
- UI/Electron IPC ถูกพักไว้จนกว่า CLI contracts จะเสถียร

## 3. ลำดับการพัฒนา

### Phase 0: Baseline และ Test Harness

ระยะเวลาเป้าหมาย: 1-2 วัน

งาน:

- เพิ่ม `pytest` สำหรับ backend และ test runner ของ frontend
- สร้าง contract test สำหรับ model namespace, IPC payload และ tool result
- สร้าง mock OpenAI-compatible endpoint เพื่อทดสอบ tool-calling โดยไม่ต้องโหลดโมเดลทุกครั้ง
- เก็บ baseline: เวลาเริ่มตอบ, tokens/second โดยประมาณ, อัตรา tool call สำเร็จ และ VRAM

เกณฑ์ผ่าน:

- รัน backend tests, frontend tests และ production build ด้วยคำสั่งเดียวได้
- การทดสอบไม่ขึ้นกับสถานะของ LM Studio ยกเว้นชุด integration test
- มี baseline report สำหรับเปรียบเทียบการเปลี่ยนแปลงครั้งถัดไป

### Phase 1: Permission Gate และ Workspace Sandbox

ระยะเวลาเป้าหมาย: 2-4 วัน

งาน:

- สร้าง `permissions/policy.py`
- สร้าง `permissions/path_guard.py`
- สร้าง `permissions/secret_guard.py`
- กำหนด workspace roots แบบ allowlist และ canonical path validation
- ป้องกัน path traversal, symlink escape และการเข้าถึง path ระบบ
- ป้องกันไฟล์ลับ เช่น `.env`, private keys, credential stores และโฟลเดอร์ผู้ใช้ที่ไม่อนุญาต
- แบ่งระดับสิทธิ์เป็น read, write, execute และ network
- เพิ่ม approval flow สำหรับการเขียนไฟล์ พร้อม diff preview และ atomic backup
- บันทึกเหตุการณ์ allow/deny ลง audit log

เกณฑ์ผ่าน:

- Unit test ยืนยันว่า `..`, absolute path นอก workspace และ symlink escape ถูกปฏิเสธ
- Agent เขียนไฟล์ไม่ได้หากยังไม่มี approval token
- ผู้ใช้เห็นไฟล์ที่จะเปลี่ยนและ diff ก่อนอนุมัติ
- ทุกการปฏิเสธและอนุมัติมี audit event

### Phase 2: Cowork Tool Registry และ Verification Tools

Status 2026-06-12: CLI slice complete. `developer_tools.py` now provides secret-aware read-only Git status/diff and approval-gated verification presets (`python-tests`, `frontend-tests`, `frontend-build`). Arbitrary shell command strings remain unavailable to the model. Workspace writes and verification runs emit structured audit events, verification timeout handling invokes process-tree cleanup, restore/list rollback backup tools exist, and cleanup is covered by deterministic Python and npm worker-tree tests. Remaining Phase 2 hardening: additional lint/typecheck presets when they are explicitly defined.

ระยะเวลาเป้าหมาย: 3-5 วัน

งาน:

- ขยาย Cowork-owned tool registry จาก `workspace_tools.py` ไปยัง Git และ verification tools
- สร้าง registry ที่ระบุชื่อ schema, permission, timeout และ handler ของแต่ละ tool
- แยก Blender tools ออกจาก Cowork tools อย่างชัดเจน
- เพิ่ม Git status, Git diff และ changed-files tools แบบ read-only ก่อน
- เพิ่ม test, lint และ typecheck runner แบบ command allowlist
- คืนผล tool เป็น structured JSON ที่มี status, stdout, stderr, duration และ changed files
- ยังไม่เปิด arbitrary shell command

เกณฑ์ผ่าน:

- Cowork เห็นเฉพาะ tools ที่เกี่ยวกับงานพัฒนาโปรแกรม
- ทุก tool มี permission class และ timeout
- Agent เรียก test/lint ได้ แต่สั่งคำสั่งนอก allowlist ไม่ได้
- Tool failure ไม่ทำให้ agent loop ล่มและมีข้อมูลพอสำหรับซ่อมงาน

### Phase 3: Agent State Machine

Status 2026-06-12: first CLI controller slice complete. `agent_state.py` records Inspect/Plan/Act/Verify/Report stage transitions, blocks final reporting after writes until `run_verification` passes, and records completion evidence. Remaining Phase 3 hardening: resumable state across sessions, richer repair loops for failed verification, and UI visibility for state/evidence.

Status 2026-06-12 restore update: rollback backups now have an approval-gated `restore_backup` tool. The restore target is inferred from `.cowork/backups/<timestamp>/...`, the current file is backed up before restoration, and restore operations are treated as file writes that require verification before final reporting.

Status 2026-06-12 hardening update: `AgentRunState` can serialize/restore JSON-safe snapshots and `CoworkAgent.run()` can resume from a prior state while preserving the post-write verification gate. `ipc_sidecar.py` now provides the Cowork-owned JSONL sidecar adapter over the stable standalone agent interface. Remaining Phase 3/UI work: richer failed-verification repair loops and UI visibility for state/evidence.

Status 2026-06-13 UI safety update: Electron now supports approval-ID request/response prompts for file writes and allowlisted verification commands. The React shell shows proposal details before Approve/Deny, while Projects, model/effort, composer, and recent-session controls provide the local Claude-like workspace shell. Remaining Phase 3/UI work: deeper Code/Cowork panels, verification output, backup restore, agent-stage visibility, and resume controls.

Status 2026-06-13 workspace panel update: Code/Cowork modes now provide lazy file browsing, guarded text preview, Git status/diff evidence, allowlisted verification output, and approval-gated backup restoration. Electron only activates workspace roots selected through its native folder dialog. Remaining Phase 3/UI work: agent-stage visibility, resumable state controls, richer repair progress, and backend-log history.

ระยะเวลาเป้าหมาย: 3-5 วัน

วงจรหลัก:

`Inspect -> Plan -> Act -> Observe -> Repair -> Verify -> Report`

งาน:

- แยก controller, state, prompts และ tool execution ออกจากกัน
- เพิ่ม budget สำหรับจำนวนรอบ, tool calls, file writes และเวลา
- รองรับ cancellation, timeout และ resumable session
- บังคับให้ Agent สรุปแผนก่อนแก้หลายไฟล์
- เมื่อเครื่องมือล้มเหลว ให้จัดประเภทข้อผิดพลาดก่อนลองใหม่
- ใช้ custom Python controller ต่อไปก่อน ยังไม่เพิ่ม LangGraph

เกณฑ์ผ่าน:

- Agent หยุดได้อย่างปลอดภัยเมื่อเกิน budget
- Session ที่ถูกยกเลิกไม่ทิ้งไฟล์ครึ่งหนึ่ง
- รายงานท้ายงานแยกสิ่งที่แก้ ผลตรวจสอบ และสิ่งที่ยังไม่แน่ใจ

### Phase 4: Repository Map และ Context Builder

ระยะเวลาเป้าหมาย: 4-7 วัน

งาน:

- ใช้ `rg` สำหรับค้นหาไฟล์และข้อความ
- ใช้ Python AST และ parser ของ JS/TS เพื่อสร้าง symbol/import map
- เชื่อมไฟล์ source, tests, config และ entry points
- เก็บ index แบบ incremental ใน SQLite โดยอัปเดตเฉพาะไฟล์ที่เปลี่ยน
- สร้าง context pack ตาม task แทนการส่งทั้ง repository
- เพิ่ม context budget, deduplication และ compaction

เกณฑ์ผ่าน:

- คำถามเกี่ยวกับ symbol สำคัญหาไฟล์ที่เกี่ยวข้องได้โดยไม่สแกนทั้ง repo ทุกครั้ง
- การแก้ไฟล์หนึ่งไฟล์อัปเดต index เฉพาะส่วนที่กระทบ
- วัด context size และเวลา retrieval ได้

### Phase 5: Structured Memory และ Experience Store

ระยะเวลาเป้าหมาย: 4-6 วัน

ระดับข้อมูล:

- Project memory: conventions, commands, architecture และข้อห้าม
- Session memory: แผน เหตุการณ์ tool call และผลตรวจสอบของงานปัจจุบัน
- Experience memory: ปัญหา วิธีแก้ และหลักฐานว่าผ่าน

งาน:

- ใช้ SQLite เป็นแหล่งข้อมูลหลัก
- ใช้ SQLite FTS สำหรับค้นหาข้อความก่อน
- เพิ่ม retention policy และคำสั่งลบ/ส่งออกข้อมูล
- เก็บ experience เฉพาะงานที่ผ่าน verification หรือผู้ใช้ยอมรับ
- ประเมิน vector retrieval หลังมี benchmark เท่านั้น

เกณฑ์ผ่าน:

- Agent จำคำสั่ง build/test และ conventions ของโปรเจกต์ข้าม session ได้
- ข้อมูลผิดหรือเก่าสามารถแก้และลบได้
- Memory ที่นำกลับมาใช้มี source และ timestamp

### Phase 6: Reviewer และ Completion Gate

ระยะเวลาเป้าหมาย: 3-5 วัน

งาน:

- แยกบทบาท Worker และ Reviewer แม้เริ่มจากโมเดลเดียวกันแบบเรียกตามลำดับ
- Reviewer ตรวจ diff, tests, security, regressions และความครบของคำขอ
- Completion Gate ต้องเห็นผล verification ล่าสุดก่อนให้สถานะสำเร็จ
- หาก test ไม่ผ่าน Agent ต้องรายงานตรงไปตรงมา ไม่เปลี่ยนเป็นข้อความสำเร็จ

เกณฑ์ผ่าน:

- งานแก้โค้ดทุกงานมี diff review และ verification record
- Completion claim อ้างอิง command และผลที่เพิ่งรันจริง
- มีสถานะชัดเจน: completed, partial, blocked หรือ cancelled

### Phase 7: Observability และ Evaluation

ระยะเวลาเป้าหมาย: 3-5 วัน

งาน:

- เก็บ session, tool calls, latency, model, errors และ file changes ใน SQLite
- สร้างหน้า timeline สำหรับดูว่า Agent ตัดสินใจและทำอะไร
- สร้าง benchmark 20-50 งานจาก repository จริง
- แยกชุดงาน read-only, bug fix, refactor, test creation และ multi-file change
- เพิ่ม regression run สำหรับ prompt, model และ tool changes

ตัวชี้วัดหลัก:

- Task success rate
- Test pass rate หลังแก้
- Tool-call validity rate
- Unsafe action block rate
- User approval/acceptance rate
- Median latency และจำนวนรอบต่อ task
- Regression rate บน benchmark เดิม

### Phase 8: Web, MCP และ Vision

เริ่มเมื่อ Phase 1-7 มีเสถียรภาพ

งาน:

- เพิ่ม URL reader ที่แยกเนื้อหาภายนอกออกจาก system instructions
- ป้องกัน prompt injection จากเว็บ เอกสาร และ tool output
- เพิ่ม MCP adapter โดยใช้ permission policy เดียวกับ local tools
- เพิ่ม image/diagram understanding เมื่อมี use case และโมเดลรองรับ

### Phase 9: Local Model Routing และ Performance

งาน:

- แยก fast model สำหรับ classification/routing และ coder model สำหรับแก้โค้ด
- เปรียบเทียบโมเดลด้วย benchmark เดียวกัน ไม่เลือกจากชื่อหรือความนิยมอย่างเดียว
- ปรับ context, quantization และ concurrency จากข้อมูล VRAM/latency จริง
- เพิ่ม fallback policy เมื่อ local model ไม่ผ่านเกณฑ์หรือ context ไม่พอ
- Cloud fallback ต้องเป็น opt-in และแสดงข้อมูลที่จะส่งก่อน

ข้อเสนอสำหรับเครื่องปัจจุบัน:

- ใช้โมเดล 7B quantized เป็น baseline ต่อไป
- ลด parallel requests จาก 6 เป็น 1 ระหว่างพัฒนาเพื่อลด VRAM pressure และผลลัพธ์ที่แกว่ง
- เริ่ม context ที่ 12K-16K แทน 21.5K แล้ววัดคุณภาพและความเร็ว
- ให้ Repository Map ลด context ที่ต้องส่ง แทนการเพิ่ม context window อย่างเดียว
- ยังไม่ใช้ embedding model ใน critical path จนกว่า SQLite FTS baseline จะแสดงข้อจำกัด

### Phase 10: Fine-tuning / LoRA

ทำเมื่อมี accepted-and-verified tasks อย่างน้อยประมาณ 500 งาน และมี evaluation set ที่แยกจาก training data

งาน:

- สร้าง dataset จาก task, context, tool calls, diff, verification และ user feedback
- กรองข้อมูลลับและงานที่ไม่ผ่าน
- เทียบ LoRA กับ prompt/RAG/tooling baseline
- version model, dataset และ rollback ได้

ไม่ควรทำ LoRA ตอนนี้ เพราะข้อจำกัดหลักยังอยู่ที่ permission, context selection, tools และ verification มากกว่าความรู้เฉพาะของโมเดล

## 4. Sprint แรก: Safety Foundation

เป้าหมาย 10 วันทำงาน:

1. เพิ่ม backend/frontend test harness และ mock local model endpoint
2. สร้าง path guard และ secret guard พร้อม malicious-path tests
3. แยก Cowork tool registry และ standalone sidecar ออกจาก Blender host
4. เพิ่ม approval token, diff preview และ atomic file write
5. เพิ่ม Git diff และ allowlisted test runner
6. เพิ่ม audit log ของ model/tool/file events
7. เพิ่ม UI สำหรับอนุมัติหรือปฏิเสธการเขียนไฟล์
8. รัน integration scenario: อ่าน issue -> วางแผน -> แก้ไฟล์ -> ขออนุมัติ -> ทดสอบ -> รายงาน

Definition of Done ของ Sprint:

- ไม่มี tool ใดอ่านหรือเขียนออกนอก workspace ได้โดยไม่ผ่าน policy
- การเขียนไฟล์ทุกครั้งต้องมี approval และแสดง diff
- Backend tests, frontend tests และ build ผ่าน
- Integration scenario ทำซ้ำได้และมี audit timeline ครบ
- เอกสาร architecture และ threat model ตรงกับพฤติกรรมจริง

## 5. Skills ที่ใช้กับโครงการ

- `writing-plans`: แตกงานเป็นขั้นตอนเล็กพร้อมไฟล์และ verification
- `improve-codebase-architecture`: ออกแบบ module boundaries และลด coupling
- `systematic-debugging`: หา root cause ก่อนแก้และเก็บหลักฐาน
- `test-driven-development`: พัฒนา permission และ tools ด้วย red-green-refactor
- `verification-before-completion`: บังคับหลักฐานก่อนประกาศว่างานเสร็จ
- `requesting-code-review`: ใช้กับ Reviewer phase และการจัดระดับความเสี่ยง
- `webapp-testing`: ทดสอบ Electron/React UI และ approval flow
- `find-skills`: ค้นหา workflow เพิ่มเติมเมื่อมีความต้องการใหม่

Skills เหล่านี้เป็นกระบวนการพัฒนา ไม่ถูกโหลดเข้า runtime ของผู้ใช้ปลายทางโดยตรง จึงไม่เพิ่มภาระให้ Local AI ในโปรแกรม

## 6. สิ่งที่ยังไม่ควรทำ

- ไม่ย้ายไป LangGraph จนกว่า custom state machine จะติดข้อจำกัดที่วัดได้
- ไม่เปิด arbitrary shell หรือ unrestricted network access
- ไม่เพิ่ม Vector DB ก่อนพิสูจน์ว่า SQLite FTS และ repo map ไม่พอ
- ไม่ทำ multi-agent พร้อมกันบน VRAM 8GB; เริ่มจากเรียก Worker/Reviewer ตามลำดับ
- ไม่ fine-tune ก่อนมีข้อมูลที่ผ่าน verification จำนวนมากพอ
- ไม่ใช้จำนวน tool calls หรือความยาวคำตอบเป็นตัวแทนคุณภาพ

## 7. Milestone ที่เสนอ

- M1 Safe Operator: Phase 0-2 เสร็จ Agent ทำงานกับไฟล์อย่างปลอดภัย
- M2 Reliable Developer: Phase 3-4 เสร็จ Agent วางแผนและเข้าใจ repository ได้ดีขึ้น
- M3 Learning Co-worker: Phase 5-7 เสร็จ Agent จำ ตรวจทาน และวัดคุณภาพตัวเองได้
- M4 Extensible Platform: Phase 8-9 เสร็จ รองรับ MCP/Web/Vision และ model routing
- M5 Specialized Model: Phase 10 เสร็จเมื่อข้อมูลและผลประเมินรองรับการ fine-tune
