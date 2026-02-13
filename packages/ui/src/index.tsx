import React from "react";

export function Card(props: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ border: "1px solid #d7ddcf", borderRadius: 12, padding: 12 }}>
      <h3>{props.title}</h3>
      <div>{props.children}</div>
    </section>
  );
}

