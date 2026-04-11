'use client';

import { useState } from 'react';
import type { PromptResult } from '../../lib/api';

interface PromptTableProps {
  prompts: PromptResult[];
}

export default function PromptTable({ prompts }: PromptTableProps) {
  const [expanded, setExpanded] = useState<{[key: number]: boolean}>({});

  const toggleExpand = (index: number) => {
    setExpanded(prev => ({ ...prev, [index]: !prev[index] }));
  };

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Prompts</h2>
      
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b">
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Prompt</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Model</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Mentions</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Date</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {prompts.map((prompt, index) => (
              <tr key={prompt.id || index} className="hover:bg-gray-50 cursor-pointer" onClick={() => toggleExpand(index)}>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    prompt.is_success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {prompt.is_success ? 'Success' : 'No mention'}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900 max-w-xs truncate" title={prompt.prompt}>
                  {prompt.prompt}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {prompt.model_name}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {Object.keys(prompt.mentions).join(', ') || 'None'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {new Date(prompt.detected_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {expanded && Object.entries(expanded).filter(([, v]) => v).map(([idx]) => {
        const prompt = prompts[Number(idx)];
        if (!prompt) return null;
        return (
          <div key={`detail-${idx}`} className="mt-3 bg-gray-50 p-3 rounded border">
            <p className="text-sm font-medium text-gray-900 mb-1">Full Prompt:</p>
            <p className="text-sm text-gray-700 mb-2">{prompt.prompt}</p>
            <p className="text-sm font-medium text-gray-900 mb-1">Response:</p>
            <p className="text-sm text-gray-700 whitespace-pre-wrap">{prompt.response_text}</p>
          </div>
        );
      })}

      {prompts.length === 0 && (
        <p className="text-center text-gray-700 py-4">No prompts available</p>
      )}
    </div>
  );
}
