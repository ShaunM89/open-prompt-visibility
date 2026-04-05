'use client';

import { useState } from 'react';

interface PromptProps {
  prompts: Array<{
    prompt: string;
    response_text: string;
    detected_models: Array<{
      model_name: string;
      model_provider: string;
      mentioned: boolean;
      timestamp: string;
    }>;
    mentions_str: string;
    completed_at: string;
  }>;
}

export default function PromptTable({ prompts }: PromptProps) {
  const [expandedModel, setExpandedModel] = useState<{[key: number]: string | null}>({});

  const handleToggle = (index: number, model: string) => {
    setExpandedModel(prev => ({
      ...prev,
      [index]: prev[index] === model ? null : model
    }));
  };

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Prompts</h2>
      
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b">
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Prompt</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Response</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Models Detected</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mentions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {prompts.map((prompt, index) => (
              <tr key={index} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm text-gray-600">
                  {new Date(prompt.completed_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900 max-w-xs truncate" title={prompt.prompt}>
                  {prompt.prompt}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600 max-w-md truncate" title={prompt.response_text}>
                  {prompt.response_text}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {prompt.detected_models.map((model, i) => (
                    <span
                      key={i}
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium mr-1 mb-1 cursor-pointer ${
                        model.mentioned ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                      }`}
                      onClick={() => handleToggle(index, model.model_name)}
                    >
                      {model.model_name}
                      {expandedModel[index] === model.model_name && (
                        <span className="ml-1 text-xs">(no mention)</span>
                      )}
                    </span>
                  ))}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {prompt.mentions_str}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {prompts.length === 0 && (
        <p className="text-center text-gray-500 py-4">No prompts available</p>
      )}
    </div>
  );
}
