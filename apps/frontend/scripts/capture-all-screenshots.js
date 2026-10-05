#!/usr/bin/env node
/**
 * Screenshot generator for all QLoot routes.
 *
 * Rules:
 *  - Captures every single route (public, student, teacher, admin).
 *  - Splits tall/scrollable pages into viewport-height screens (never single fullPage strips).
 *  - Saves output to docs/screenshot/ with clear sequential names.
 */

import { chromium } from '@playwright/test';
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '../../..');
const OUTPUT_DIR = path.resolve(ROOT_DIR, 'docs', 'screenshot');
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const VIEWPORT_WIDTH = 1280;
const VIEWPORT_HEIGHT = 800;

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function getDbEntities() {
  const query = `
    SELECT 'course:' || id FROM courses LIMIT 1;
    SELECT 'lesson:' || l.id || '|' || l.course_id FROM lessons l JOIN courses c ON l.course_id = c.id LIMIT 1;
    SELECT 'exam:' || id FROM exams LIMIT 1;
    SELECT 'quest:' || id FROM quests LIMIT 1;
    SELECT 'room:' || id FROM rooms LIMIT 1;
    SELECT 'cert:' || credential_id FROM certificates LIMIT 1;
    SELECT 'material:' || id FROM learning_materials LIMIT 1;
    SELECT 'attempt:' || a.id || '|' || a.exam_id FROM exam_attempts a JOIN users u ON a.user_id = u.id WHERE u.email = 'student1@qloot.example' LIMIT 1;
  `;
  try {
    const raw = execSync(
      `docker compose exec -T postgres psql -U qloot -d qloot -t -A -c "${query}"`,
      { cwd: ROOT_DIR, encoding: 'utf-8' }
    );
    const lines = raw.trim().split('\n');
    const res = {};
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const [type, val] = trimmed.split(':');
      if (type === 'course') res.courseId = val;
      if (type === 'lesson') {
        const [lid, cid] = val.split('|');
        res.lessonId = lid;
        if (!res.courseId) res.courseId = cid;
      }
      if (type === 'exam') res.examId = val;
      if (type === 'quest') res.questId = val;
      if (type === 'room') res.roomId = val;
      if (type === 'cert') res.credentialId = val;
      if (type === 'material') res.materialId = val;
      if (type === 'attempt') {
        const [aid, eid] = val.split('|');
        res.attemptId = aid;
        if (!res.examId) res.examId = eid;
      }
    }
    return res;
  } catch (err) {
    console.warn('Could not query DB dynamically, using fallback UUIDs:', err.message);
    return {
      courseId: 'f025c529-ef23-4b48-99ce-10f1e7226c83',
      lessonId: '8d5d32c9-b26c-47f4-b3df-7bdbe660ab6a',
      examId: 'ec907a5e-d8e0-47c4-9c7f-052ead6eafb0',
      questId: '46013b7d-d4c5-464c-ae95-de77b525187e',
      roomId: 'db194ad9-7639-4343-b911-90134a385f58',
      credentialId: 'QLT-MATK1-0001-3D5506',
      materialId: 'e33de57b-ea58-4ba9-889e-f806af5167d7',
      attemptId: 'c94b80e3-5a21-4677-8fcb-d79277388735',
    };
  }
}

async function captureMultiScreen(page, routePath, filePrefix) {
  const url = `${BASE_URL}${routePath}`;
  console.log(`\n📸 [${filePrefix}] Capturing: ${url}`);
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
  } catch (e) {
    console.log(`  (Network idle wait finished/timed out, continuing)`);
  }

  // Allow animations and client-side store sync to settle
  await page.waitForTimeout(600);
  try {
    await page.evaluate(() => document.fonts?.ready);
  } catch {}

  // Measure total scroll height
  const scrollHeight = await page.evaluate(() => {
    const body = document.body;
    const html = document.documentElement;
    return Math.max(
      body ? body.scrollHeight : 0,
      body ? body.offsetHeight : 0,
      html ? html.clientHeight : 0,
      html ? html.scrollHeight : 0,
      html ? html.offsetHeight : 0
    );
  });

  const positions = [];
  if (scrollHeight <= VIEWPORT_HEIGHT) {
    positions.push(0);
  } else {
    for (let y = 0; y < scrollHeight; y += VIEWPORT_HEIGHT) {
      positions.push(Math.min(y, scrollHeight - VIEWPORT_HEIGHT));
      if (y + VIEWPORT_HEIGHT >= scrollHeight) break;
    }
  }
  const uniquePositions = [...new Set(positions)];

  console.log(`  Height: ${scrollHeight}px -> splitting into ${uniquePositions.length} screen(s)`);

  for (let idx = 0; idx < uniquePositions.length; idx++) {
    const pos = uniquePositions[idx];
    await page.evaluate((y) => window.scrollTo(0, y), pos);
    await page.waitForTimeout(350);

    const filename =
      uniquePositions.length === 1
        ? `${filePrefix}.png`
        : `${filePrefix}_part_${String(idx + 1).padStart(2, '0')}.png`;

    const destPath = path.join(OUTPUT_DIR, filename);
    await page.screenshot({ path: destPath, fullPage: false });
    console.log(`    ✓ Saved: ${filename}`);
  }
}

async function loginUser(page, email, password) {
  console.log(`\n🔑 Authenticating as: ${email}`);
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1500);
}

async function main() {
  ensureDir(OUTPUT_DIR);
  console.log('Target screenshot directory:', OUTPUT_DIR);

  const entities = getDbEntities();
  console.log('Database entity IDs resolved:');
  console.dir(entities);

  const browser = await chromium.launch();

  try {
    // =========================================================================
    // 1. PUBLIC ROUTES (Unauthenticated)
    // =========================================================================
    console.log('\n==================================================');
    console.log('>>> SECTION 1: PUBLIC ROUTES');
    console.log('==================================================');
    const publicContext = await browser.newContext({
      viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
    });
    const publicPage = await publicContext.newPage();

    const publicRoutes = [
      { prefix: '01_landing', path: '/' },
      { prefix: '02_about', path: '/about' },
      { prefix: '03_login', path: '/login' },
      { prefix: '04_register', path: '/register' },
      { prefix: '05_forgot_password', path: '/forgot-password' },
      { prefix: '06_reset_password', path: '/reset-password' },
      { prefix: '07_blog', path: '/blog' },
      { prefix: '08_business', path: '/business' },
      { prefix: '09_careers', path: '/careers' },
      { prefix: '10_faq', path: '/faq' },
      { prefix: '11_legal', path: '/legal' },
    ];

    for (const r of publicRoutes) {
      await captureMultiScreen(publicPage, r.path, r.prefix);
    }
    await publicContext.close();

    // =========================================================================
    // 2. STUDENT ROUTES (Authenticated as student)
    // =========================================================================
    console.log('\n==================================================');
    console.log('>>> SECTION 2: STUDENT ROUTES');
    console.log('==================================================');
    const studentContext = await browser.newContext({
      viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
    });
    const studentPage = await studentContext.newPage();
    await loginUser(studentPage, 'student1@qloot.example', 'StudentPass123!');

    const studentRoutes = [
      { prefix: '12_student_dashboard', path: '/dashboard' },
      { prefix: '13_student_learning_hub', path: '/learning' },
      { prefix: '14_student_learning_course', path: `/learning/${entities.courseId}` },
      { prefix: '15_student_learning_lesson', path: `/learning/${entities.courseId}/lesson/${entities.lessonId}` },
      { prefix: '16_student_courses_catalog', path: '/courses' },
      { prefix: '17_student_course_detail', path: `/courses/${entities.courseId}` },
      { prefix: '18_student_paths', path: '/paths' },
      { prefix: '19_student_exams_hub', path: '/exams' },
      { prefix: '20_student_exam_detail', path: `/exams/${entities.examId}` },
      { prefix: '21_student_exam_attempt', path: `/exams/${entities.examId}/attempt?attempt=${entities.attemptId}` },
      { prefix: '22_student_exam_result', path: `/exams/${entities.examId}/result?attempt=${entities.attemptId}` },
      { prefix: '23_student_quests', path: '/quests' },
      { prefix: '24_student_tasks', path: '/tasks' },
      { prefix: '25_student_rooms', path: '/rooms' },
      { prefix: '26_student_room_detail', path: `/rooms/${entities.roomId}` },
      { prefix: '27_student_ranking', path: '/ranking' },
      { prefix: '28_student_badges', path: '/badges' },
      { prefix: '29_student_certificates', path: '/certificates' },
      { prefix: '30_student_verify_credential', path: `/verify/${entities.credentialId}` },
      { prefix: '31_student_community', path: '/community' },
      { prefix: '32_student_career_hub', path: '/career' },
      { prefix: '33_student_career_library', path: '/career/library' },
      { prefix: '34_student_career_personality', path: '/career/personality' },
      { prefix: '35_student_career_roadmap', path: '/career/roadmap' },
      { prefix: '36_student_career_consultation', path: '/career/consultation' },
      { prefix: '37_student_assistant', path: '/assistant' },
      { prefix: '38_student_wallet', path: '/wallet' },
      { prefix: '39_student_profile', path: '/profile' },
      { prefix: '40_student_notifications', path: '/notifications' },
    ];

    for (const r of studentRoutes) {
      await captureMultiScreen(studentPage, r.path, r.prefix);
    }
    await studentContext.close();

    // =========================================================================
    // 3. TEACHER ROUTES (Authenticated as teacher)
    // =========================================================================
    console.log('\n==================================================');
    console.log('>>> SECTION 3: TEACHER ROUTES');
    console.log('==================================================');
    const teacherContext = await browser.newContext({
      viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
    });
    const teacherPage = await teacherContext.newPage();
    await loginUser(teacherPage, 'teacher@qloot.example', 'TeacherPass123!');

    const teacherRoutes = [
      { prefix: '41_teacher_dashboard', path: '/teacher' },
      { prefix: '42_teacher_subjects', path: '/teacher/subjects' },
      { prefix: '43_teacher_subject_new', path: '/teacher/subjects/new' },
      { prefix: '44_teacher_subject_detail', path: `/teacher/subjects/${entities.courseId}` },
      { prefix: '45_teacher_materials', path: '/teacher/materials' },
      { prefix: '46_teacher_material_detail', path: `/teacher/materials/${entities.materialId}` },
      { prefix: '47_teacher_exams', path: '/teacher/exams' },
      { prefix: '48_teacher_exam_new', path: '/teacher/exams/new' },
      { prefix: '49_teacher_exam_detail', path: `/teacher/exams/${entities.examId}` },
      { prefix: '50_teacher_exam_results', path: `/teacher/exams/${entities.examId}/results` },
      { prefix: '51_teacher_submissions', path: '/teacher/submissions' },
      { prefix: '52_teacher_quests', path: '/teacher/quests' },
      { prefix: '53_teacher_quest_new', path: '/teacher/quests/new' },
      { prefix: '54_teacher_quest_detail', path: `/teacher/quests/${entities.questId}` },
      { prefix: '55_teacher_tasks', path: '/teacher/tasks' },
      { prefix: '56_teacher_rankings', path: '/teacher/rankings' },
      { prefix: '57_teacher_resources', path: '/teacher/resources' },
      { prefix: '58_teacher_consultations', path: '/teacher/consultations' },
    ];

    for (const r of teacherRoutes) {
      await captureMultiScreen(teacherPage, r.path, r.prefix);
    }
    await teacherContext.close();

    // =========================================================================
    // 4. ADMIN ROUTES (Authenticated as admin)
    // =========================================================================
    console.log('\n==================================================');
    console.log('>>> SECTION 4: ADMIN ROUTES');
    console.log('==================================================');
    const adminContext = await browser.newContext({
      viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT },
    });
    const adminPage = await adminContext.newPage();
    await loginUser(adminPage, 'admin@qloot.example', 'AdminPass123!');

    const adminRoutes = [
      { prefix: '59_admin_dashboard', path: '/admin' },
      { prefix: '60_admin_users', path: '/admin/users' },
      { prefix: '61_admin_user_new', path: '/admin/users/new' },
      { prefix: '62_admin_blockchain', path: '/admin/blockchain' },
      { prefix: '63_admin_blockchain_transactions', path: '/admin/blockchain/transactions' },
      { prefix: '64_admin_blockchain_events', path: '/admin/blockchain/events' },
      { prefix: '65_admin_rewards', path: '/admin/rewards' },
      { prefix: '66_admin_ledger', path: '/admin/ledger' },
      { prefix: '67_admin_leaderboards', path: '/admin/leaderboards' },
      { prefix: '68_admin_moderation', path: '/admin/moderation' },
      { prefix: '69_admin_notifications', path: '/admin/notifications' },
      { prefix: '70_admin_withdrawals', path: '/admin/withdrawals' },
      { prefix: '71_admin_audit', path: '/admin/audit' },
      { prefix: '72_admin_config', path: '/admin/config' },
    ];

    for (const r of adminRoutes) {
      await captureMultiScreen(adminPage, r.path, r.prefix);
    }
    await adminContext.close();

    console.log('\n🎉 ALL 72 ROUTES SCREENSHOTTED SUCCESSFULLY!');
    const files = fs.readdirSync(OUTPUT_DIR).filter((f) => f.endsWith('.png'));
    console.log(`Total screenshot images generated: ${files.length}`);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error('Fatal error during screenshot capture:', err);
  process.exit(1);
});
