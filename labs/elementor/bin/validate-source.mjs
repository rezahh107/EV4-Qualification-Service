#!/usr/bin/env node
// Structural source contract for the existing Playwright/Elementor lab.
// AST nodes, not source text or comments, decide who may create qualification steps.
import fs from 'node:fs';
import crypto from 'node:crypto';
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

// Closed grammar for actual product predicates. No unreviewed helper calls,
// browser handles, async evaluation, accessors, arbitrary globals or mutations.
const matchers = new Set(['toBe','toEqual','toMatch','toHaveLength',
  'toBeGreaterThan','toBeGreaterThanOrEqual','toBeLessThan',
  'toBeLessThanOrEqual','toBeNull']);
function pureValue(n, known) {
  if (!n) return false;
  if (n.type === 'ChainExpression') return pureValue(n.expression, known);
  if (n.type === 'Literal') return true;
  if (n.type === 'Identifier') return known.has(n.name);
  if (n.type === 'MemberExpression') {
    return pureValue(n.object, known) &&
      (n.computed ? n.property.type === 'Literal' &&
       (typeof n.property.value === 'string' || Number.isInteger(n.property.value)) :
       n.property.type === 'Identifier');
  }
  if (n.type === 'BinaryExpression' && ['+','-','*','/'].includes(n.operator))
    return pureValue(n.left, known) && pureValue(n.right, known);
  if (n.type === 'UnaryExpression' && ['-','+','!'].includes(n.operator))
    return pureValue(n.argument, known);
  if (n.type === 'ArrayExpression') return n.elements.every(x => pureValue(x, known));
  if (n.type === 'ObjectExpression')
    return n.properties.every(x => x.type === 'Property' && !x.computed &&
      pureValue(x.value, known));
  return false;
}
function canonicalSyntax(node) {
  if (Array.isArray(node)) return node.map(canonicalSyntax);
  if (!node || typeof node !== 'object') return node;
  const result={};
  for (const [key,value] of Object.entries(node)) {
    if (['start','end','raw','loc','range'].includes(key)) continue;
    result[key]=canonicalSyntax(value);
  }
  return result;
}
function predicateFingerprint(callback) {
  return crypto.createHash('sha256')
    .update(JSON.stringify(canonicalSyntax(callback.body))).digest('hex');
}
const predicateFingerprints = {};

function qualifyOnlyPlainAssertions(callback, file, identity) {
  if (callback.async || callback.generator || callback.params.length !== 1 ||
      !identifier(callback.params[0], 'snapshot') || callback.body.type !== 'BlockStatement')
    reject(file + ': unsupported async/parameterized product predicate ' + identity);
  function checkStatements(statements, known) {
    for (const stmt of statements) {
      if (stmt.type === 'ForOfStatement') {
        if (stmt.await || stmt.left?.type !== 'VariableDeclaration' ||
            stmt.left.kind !== 'const' || stmt.left.declarations.length !== 1 ||
            stmt.left.declarations[0].id.type !== 'Identifier' ||
            stmt.left.declarations[0].init ||
            !pureValue(stmt.right, known) || stmt.body.type !== 'BlockStatement')
          reject(file + ': unsupported product-predicate loop ' + identity);
        const next = new Set(known);
        next.add(stmt.left.declarations[0].id.name);
        checkStatements(stmt.body.body, next);
        continue;
      }
      const outer = stmt.type === 'ExpressionStatement' && stmt.expression;
      if (outer?.type !== 'CallExpression' || outer.optional ||
          outer.callee.type !== 'MemberExpression' ||
          !identifier(outer.callee.property, outer.callee.property.name) ||
          !matchers.has(outer.callee.property.name))
        reject(file + ': product callback contains non-predicate operation ' + identity);
      let base = outer.callee.object;
      if (memberIs(base, 'not')) base = base.object;
      if (base?.type !== 'CallExpression' || !identifier(base.callee, 'expect') ||
          !(base.arguments.length === 1 || base.arguments.length === 2) ||
          !base.arguments.every(x => pureValue(x, known)) ||
          !outer.arguments.every(x => pureValue(x, known)))
        reject(file + ': matcher reads non-data input or invokes helper ' + identity);
    }
  }
  checkStatements(callback.body.body, new Set(['snapshot']));
}

// The only permitted step authority is the existing small helper with
// one exported function, one native test.step call and a canonical title.
const helper = parseFile(path.join(testDir, 'qualification.mjs'));
const helperExports = helper.body.filter(node => node.type === 'ExportNamedDeclaration');
const fn = helperExports.length === 1 && helperExports[0].declaration;
if (!fn || fn.type !== 'FunctionDeclaration' ||
    !identifier(fn.id, 'productAssertion') || fn.params.length !== 3 ||
    !identifier(fn.params[0], 'identity') ||
    !identifier(fn.params[1], 'observation') ||
    !identifier(fn.params[2], 'assertProduct'))
  reject('Qualification helper has invalid public qualification signature');
const nativeTestImports = helper.body.filter(node=>node.type === 'ImportDeclaration' &&
  node.source.value === '@playwright/test');
if (nativeTestImports.length !== 1 ||
    !nativeTestImports[0].specifiers.some(x => x.type === 'ImportSpecifier' &&
       identifier(x.imported,'test') && identifier(x.local,'test')))
  reject('Qualification helper must bind native Playwright test');
let reservedSteps = 0;
walk(fn.body, node=>{
  if (node.type !== 'CallExpression' || !memberIs(node.callee,'step')) return;
  reservedSteps++;
  const [title] = node.arguments;
  if (!identifier(node.callee.object,'test') ||
      title?.type !== 'BinaryExpression' || title.operator !== '+' ||
      !literal(title.left, prefix) || !identifier(title.right,'identity'))
    reject('Qualification helper has noncanonical step identity');
});
if (reservedSteps !== 1) reject('Qualification helper requires exactly one native Step');

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
    if (!['@playwright/test', 'node:fs', 'node:path', 'node:crypto', './helpers.mjs', './qualification.mjs', './observation.mjs'].includes(src))
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
    if (isSpec && node.type === 'Identifier' && node.name === 'test' &&
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
  const acquisitions = [];
  walk(ast, node => {
    if (node.type !== 'VariableDeclarator' ||
        !identifier(node.id,'observation') ||
        node.init?.type !== 'AwaitExpression' ||
        node.init.argument.type !== 'CallExpression' ||
        !identifier(node.init.argument.callee,'observe')) return;
    const acquisition = node.init.argument;
    if (acquisition.arguments.length !== 2 ||
        acquisition.arguments[0].type !== 'Literal' ||
        acquisition.arguments[1].type !== 'ArrowFunctionExpression' ||
        !acquisition.arguments[1].async)
      reject(file + ': invalid observation acquisition');
    const parentTests = ownTests.filter(t =>
      node.start >= t.callback.start && node.end <= t.callback.end);
    if (parentTests.length !== 1 ||
        acquisition.arguments[0].value !== parentTests[0].identity)
      reject(file + ': observation identity/scope mismatch');
    acquisitions.push(acquisition.arguments[0].value);
  });
  const qualificationCalls = [];
  walk(ast, (node, parent) => {
    if (node.type !== 'CallExpression' || !identifier(node.callee, 'productAssertion')) return;
    if (!isSpec || !hasAuthorizedHelper || parent?.type !== 'AwaitExpression')
      reject(file + ': unauthorized or unawaited productAssertion');
    if (node.arguments.length !== 3 || node.arguments[0].type !== 'Literal' ||
        !qualifiedOrigin(node.arguments[0].value) ||
        !identifier(node.arguments[1], 'observation') ||
        node.arguments[2].type !== 'ArrowFunctionExpression')
      reject(file + ': malformed data-only qualification invocation');
    qualifyOnlyPlainAssertions(node.arguments[2], file, node.arguments[0].value);
    predicateFingerprints[node.arguments[0].value] = predicateFingerprint(node.arguments[2]);
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
    if (acquisitions.filter(id => id === t.identity).length !== 1)
      reject(t.identity + ': exactly one acquired observation required');
    declarations.set(t.identity, file);
  }
  if (qualificationCalls.length !== ownTests.length || acquisitions.length !== ownTests.length)
    reject(file + ': ambiguous qualification call/declaration count');
}
if (!sawTestFile || declarations.size !== expected.size ||
    [...declarations.keys()].some(id => !expected.has(id)))
  reject('Executable test declarations do not match catalog identities');
process.stdout.write(JSON.stringify({
  qualified:[...declarations.keys()].sort(),
  predicate_fingerprints:predicateFingerprints
}) + '\n');
