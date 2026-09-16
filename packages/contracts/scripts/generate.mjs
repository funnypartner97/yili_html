import { compileFromFile } from 'json-schema-to-typescript';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('..', import.meta.url));
const check = process.argv.includes('--check');
await mkdir(path.join(root, 'src/generated'), { recursive: true });
for (const name of ['common', 'document-graph', 'generation-plan', 'edit-command', 'presentation', 'layout-registry', 'template-package', 'data-visualization']) {
  const source = await compileFromFile(path.join(root, 'schemas', name + '.schema.json'), { unreachableDefinitions: true, bannerComment: '/* Generated from canonical JSON Schema. Run pnpm --filter @html-office/contracts generate. */' });
  const target = path.join(root, 'src/generated', name + '.ts');
  if (check) {
    if (await readFile(target, 'utf8') !== source) throw new Error('Generated contract drift: ' + name + '. Run pnpm --filter @html-office/contracts generate.');
  } else {
    await writeFile(target, source);
  }
}
