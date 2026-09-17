import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>把材料变成可编辑成果</h1>
      <p>上传材料，描述目标，确认计划后生成可编辑的文档与演示。</p>
      <Link href="/create" className="primary">开始创作</Link>
    </main>
  );
}
