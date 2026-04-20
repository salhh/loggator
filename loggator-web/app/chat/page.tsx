import ChatClient from "./ChatClient";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Chat with your logs</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Ask natural language questions. Answers are grounded in your actual log data via semantic search.
        </p>
      </div>
      <ChatClient />
    </div>
  );
}
