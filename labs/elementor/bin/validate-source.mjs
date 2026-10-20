#!/usr/bin/env node
// Structural source contract for the existing Playwright/Elementor lab.
// AST nodes, not source text or comments, decide who may create qualification steps.
import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'acorn';

const root = path.resolve(process.argv[2] || '.');
const expected = new Set(JSON.parse(process.argv[3] || '[]'));
const prefix = 'EV4_PRODUCT_ASSERTION:';
const testDir = path.join(root, 'tests');

function reject(reason) { throw new Error('SOURCE_CONTRACT: ' + reason); }
function walk(node, visit, parent = null) {
  if (!node || typeof node !== 'object') return;
  if (typeof node.type === 'string') visit(node, parent);
  for (const [key, child] of Object.entries(node)) {
    if (['start', 'end', 'loc', 'range', 'raw'].includes(key)) continue;
    if (Array.isArray(child)) child.forEach(item => walk(item, visit, node));
    else if (child && typeof child === 'object') walk(child, visit, node);
  }
}
function parseFile(filename) {
  return parse(fs.readFileSync(filename, 'utf8'), {
    ecmaVersion: 2025, sourceType: 'module', allowHashBang: true
  });
}
function literal(node, value) {
  return node?.type === 'Literal' && node.value === value;
}
function identifier(node, name) {
  return node?.type === 'Identifier' && node.name === name;
}
function memberIs(node, name) {
  return node?.type === 'MemberExpression' &&
    (node.computed ? literal(node.property, name) : identifier(node.property, name));
}
function bindingNames(node) {
  if (!node) return [];
  if (node.type === 'Identifier') return [node.name];
  if (node.type === 'RestElement' || node.type === 'AssignmentPattern')
    return bindingNames(node.argument || node.left);
  if (node.type === 'ArrayPattern') return node.elements.flatMap(bindingNames);
  if (node.type === 'ObjectPattern') return node.properties.flatMap(p => bindingNames(p.value || p.argument));
  return [];
}
function qualifiedOrigin(name) {
  return typeof name === 'string' && /^[A-O]:[a-z0-9-]+$/.test(name);
}

// The only permitted step authority is the existing small helper with
// one exported function, one native test.step call and a canonical title.
const helper = parseFile(path.join(testDir, 'qualification.mjs'));
if (helper.body.length !== 2) reject('Qualification helper has unexpected top-level code');
const [helperImport, helperExport] = helper.body;
if (helperImport.type !== 'ImportDeclaration' || helperImport.source.value !== '@playwright/test' ||
    helperImport.specifiers.length !== 1 ||
    helperImport.specifiers[0].type !== 'ImportSpecifier' ||
    !identifier(helperImport.specifiers[0].imported, 'test') ||
    !identifier(helperImport.specifiers[0].local, 'test')) {
  reject('Qualification helper must import the native Playwright test binding');
}
const functionNode = helperExport.type === 'ExportNamedDeclaration' && helperExport.declaration;
if (functionNode?.type !== 'FunctionDeclaration' ||
    !identifier(functionNode.id, 'productAssertion') ||
    functionNode.params.length !== 2 ||
    !identifier(functionNode.params[0], 'identity') ||
    !identifier(functionNode.params[1], 'assertProduct')) {
  reject('Qualification helper must export the canonical productAssertion function');
}
let helperSteps = 0;
walk(functionNode.body, node => {
  if (node.type !== 'CallExpression' || !memberIs(node.callee, 'step')) return;
  helperSteps++;
  const [title, body] = node.arguments;
  if (!identifier(node.callee.object, 'test') ||
      title?.type !== 'BinaryExpression' || title.operator !== '+' ||
      !literal(title.left, prefix) || !identifier(title.right, 'identity') ||
      !identifier(body, 'assertProduct') || node.arguments.length !== 2) {
    reject('Qualification helper creates noncanonical reserved step');
  }
});
if (helperSteps !== 1) reject('Qualification helper must have exactly one reserved test.step');
const returns = [];
walk(functionNode.body, node => { if (node.type === 'ReturnStatement') returns.push(node.argument); });
if (returns.length !== 1 || returns[0]?.type !== 'CallExpression' ||
    !memberIs(returns[0].callee, 'step') ||
    !identifier(returns[0].callee.object, 'test')) {
  reject('Qualification helper must directly return the canonical native step');
}

// Every browser test is inspected: a raw test.step or an alias to .step is
// forbidden outside the helper, regardless of its argument construction.
const declarations = new Map();
const files = fs.readdirSync(testDir).filter(f => f.endsWith('.mjs') &&
  f !== 'qualification.mjs').sort();
let sawTestFile = false;
for (const file of files) {
  const ast = parseFile(path.join(testDir, file));
  const isSpec = file.endsWith('.spec.mjs');
  if (isSpec) sawTestFile = true;
  let hasNativeTest = false;
  let hasAuthorizedHelper = false;
  for (const declaration of ast.body) {
    if (declaration.type !== 'ImportDeclaration') continue;
    const src = declaration.source.value;
    if (!['@playwright/test', 'node:fs', './helpers.mjs', './qualification.mjs'].includes(src))
      reject(file + ': unknown executable import ' + src);
    if (src === '@playwright/test') {
      if (declaration.specifiers.some(s => s.type !== 'ImportSpecifier' ||
          !['test', 'expect'].includes(s.imported.name) ||
          s.local.name !== s.imported.name)) reject(file + ': Playwright import alias forbidden');
      hasNativeTest ||= declaration.specifiers.some(s => identifier(s.local, 'test'));
    }
    if (src === './qualification.mjs') {
      if (!isSpec || declaration.specifiers.length !== 1 ||
          declaration.specifiers[0].type !== 'ImportSpecifier' ||
          !identifier(declaration.specifiers[0].imported, 'productAssertion') ||
          !identifier(declaration.specifiers[0].local, 'productAssertion'))
        reject(file + ': qualification helper import must be unaliased in test spec');
      hasAuthorizedHelper = true;
    }
  }
  const ownTests = [];
  walk(ast, (node, parent) => {
    if (node.type === 'Literal' && typeof node.value === 'string' &&
        node.value.includes(prefix)) reject(file + ': forged reserved title literal');
    if (node.type === 'TemplateElement' &&
        node.value.raw.includes(prefix)) reject(file + ': forged reserved title template');
    if (node.type === 'MemberExpression' &&
        (memberIs(node, 'step') || (node.computed && identifier(node.object, 'test'))))
      reject(file + ': direct or indirect Playwright step construction forbidden');
    if (node.type === 'Property' && (identifier(node.key, 'step') || literal(node.key, 'step')))
      reject(file + ': step destructuring/alias forbidden');
    if (node.type === 'ImportExpression' ||
        (node.type === 'CallExpression' && identifier(node.callee, 'eval')) ||
        (node.type === 'NewExpression' && identifier(node.callee, 'Function')) ||
        (node.type === 'CallExpression' && identifier(node.callee, 'require')))
      reject(file + ': dynamic code loading/evaluation forbidden');
    if (node.type === 'VariableDeclarator' &&
        bindingNames(node.id).some(n => ['test', 'productAssertion'].includes(n)))
      reject(file + ': qualification binding shadowed');
    if ((node.type === 'FunctionDeclaration' || node.type === 'FunctionExpression' ||
         node.type === 'ArrowFunctionExpression') &&
        [...(node.id ? [node.id.name] : []), ...node.params.flatMap(bindingNames)]
          .some(n => ['test', 'productAssertion'].includes(n)))
      reject(file + ': qualification binding shadowed in function');
    if (node.type === 'AssignmentExpression' &&
        ['test', 'productAssertion'].some(n => identifier(node.left, n)))
      reject(file + ': qualification binding reassigned');
    if (node.type === 'Identifier' && node.name === 'productAssertion' &&
        !(parent?.type === 'ImportSpecifier' ||
          (parent?.type === 'CallExpression' && parent.callee === node)))
      reject(file + ': indirect alias/reference to productAssertion forbidden');
    if (node.type === 'Identifier' && node.name === 'test' &&
        !(parent?.type === 'ImportSpecifier' ||
          (parent?.type === 'CallExpression' && parent.callee === node)))
      reject(file + ': indirect use or alias of Playwright test binding forbidden');
    if (node.type === 'CallExpression' && identifier(node.callee, 'test')) {
      if (parent?.type !== 'ExpressionStatement' ||
          !ast.body.some(item => item.type === 'ExpressionStatement' && item.expression === node))
        reject(file + ': test declaration must be top-level');
      if (!isSpec || !hasNativeTest || node.arguments.length !== 2 ||
          node.arguments[0].type !== 'Literal' ||
          typeof node.arguments[0].value !== 'string' ||
          !node.arguments[0].value.startsWith('[') ||
          !['ArrowFunctionExpression', 'FunctionExpression'].includes(node.arguments[1].type))
        reject(file + ': invalid native test declaration');
      const match = /^\[([A-O]:[a-z0-9-]+)\]/.exec(node.arguments[0].value);
      if (!match) reject(file + ': invalid catalog test identity');
      ownTests.push({identity:match[1], callback:node.arguments[1]});
    }
  });
  if (isSpec && (!hasNativeTest || !hasAuthorizedHelper))
    reject(file + ': native test or authorized helper import missing');
  if (!isSpec && hasAuthorizedHelper) reject(file + ': unauthorized helper usage');
  const qualificationCalls = [];
  walk(ast, (node, parent) => {
    if (node.type !== 'CallExpression' || !identifier(node.callee, 'productAssertion')) return;
    if (!isSpec || !hasAuthorizedHelper || parent?.type !== 'AwaitExpression')
      reject(file + ': unauthorized or unawaited productAssertion');
    if (node.arguments.length !== 2 || node.arguments[0].type !== 'Literal' ||
        !qualifiedOrigin(node.arguments[0].value) ||
        !['ArrowFunctionExpression', 'FunctionExpression'].includes(node.arguments[1].type))
      reject(file + ': nonliteral/malformed qualification invocation');
    const containing = ownTests.filter(t => node.start >= t.callback.start &&
                                            node.end <= t.callback.end);
    if (containing.length !== 1 || containing[0].identity !== node.arguments[0].value)
      reject(file + ': qualification invocation identity or scope mismatch');
    qualificationCalls.push(node.arguments[0].value);
  });
  for (const t of ownTests) {
    if (declarations.has(t.identity)) reject('Duplicate scenario declaration: ' + t.identity);
    if (qualificationCalls.filter(id => id === t.identity).length !== 1)
      reject(t.identity + ': exactly one authorized invocation required');
    declarations.set(t.identity, file);
  }
  if (qualificationCalls.length !== ownTests.length)
    reject(file + ': ambiguous qualification call/declaration count');
}
if (!sawTestFile || declarations.size !== expected.size ||
    [...declarations.keys()].some(id => !expected.has(id)))
  reject('Executable test declarations do not match catalog identities');
process.stdout.write(JSON.stringify({qualified:[...declarations.keys()].sort()}) + '\n');
